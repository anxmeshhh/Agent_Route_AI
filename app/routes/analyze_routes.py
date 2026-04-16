"""
app/routes/analyze_routes.py — POST /analyze endpoint + background pipeline

Blueprint: analyze_bp
"""
import uuid
import time
import logging
import threading

from flask import Blueprint, request, jsonify, current_app, g

from ..agents.intake_agent import IntakeAgent
from ..database import execute_query
from ._sse import push_sse_event, mark_session_done, init_sse_session
from ._db_helpers import _store_shipment, _update_shipment_status, _log_to_db
from ..auth.decorators import login_required

logger = logging.getLogger(__name__)
analyze_bp = Blueprint("analyze", __name__)


@analyze_bp.route("/analyze", methods=["POST"])
@login_required
def analyze():
    """Start an analysis run using the agentic graph. Requires valid JWT."""
    body = request.get_json(silent=True) or {}
    query_text = (body.get("query") or "").strip()

    # Capture org_id from the JWT (set by @login_required in g)
    org_id = getattr(g, "org_id", 1)

    # ── Input validation ──────────────────────────────────────
    if not query_text:
        return jsonify({"error": "query is required"}), 400
    if len(query_text) > 1000:
        return jsonify({"error": "query too long (max 1000 chars)"}), 400
    if len(query_text) < 5:
        return jsonify({"error": "query too short — describe a shipment"}), 400

    # Strip control characters (keep newlines)
    import re as _re
    query_text = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', query_text)

    session_id = str(uuid.uuid4())
    init_sse_session(session_id)

    app = current_app._get_current_object()
    thread = threading.Thread(
        target=_run_analysis_pipeline,
        args=(app, session_id, query_text, org_id),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "session_id": session_id,
        "status": "running",
        "stream_url": f"/api/stream/{session_id}",
    })


def _run_analysis_pipeline(app, session_id: str, query_text: str, org_id: int = 1):
    """
    Runs the full agentic graph in a background thread.
    1. Intake Agent parses the query
    2. AgentGraph orchestrates all agents via LLM-based routing
    3. Results stream to UI via SSE
    org_id tags the shipment to the requesting user's organisation.
    """
    with app.app_context():
        try:
            # ── Step 1: Intake Agent ──────────────────────────
            push_sse_event(session_id, "agent_log", {
                "agent": "intake",
                "action": "🤖 Intake Agent — parsing your shipment query...",
                "status": "started",
            })

            intake = IntakeAgent()
            intake_result = intake.run(query_text, session_id)

            # Stream intake logs
            for log in intake_result.get("logs", []):
                push_sse_event(session_id, "agent_log", {
                    "agent": log["agent"],
                    "action": log["action"],
                    "status": log["status"],
                    "data": log.get("data"),
                })
                time.sleep(0.04)

            # ── Store shipment in DB ──────────────────────────
            push_sse_event(session_id, "agent_log", {
                "agent": "intake",
                "action": "Persisting shipment to MySQL...",
                "status": "started",
            })

            shipment_id = _store_shipment(session_id, intake_result, org_id)
            _log_to_db(session_id, "intake", "Shipment stored in database",
                       "success", {"shipment_id": shipment_id})

            push_sse_event(session_id, "agent_log", {
                "agent": "intake",
                "action": f"Shipment stored (ID: {shipment_id})",
                "status": "success",
            })

            # ── Step 2: Agentic Graph Execution ───────────────
            push_sse_event(session_id, "agent_log", {
                "agent": "graph",
                "action": "🧠 Agentic Graph — LLM Router deciding agent sequence...",
                "status": "started",
            })
            from ..agents.graph import AgentGraph
            graph = AgentGraph(
                session_id=session_id,
                push_event=push_sse_event,
                config=app.config,
                db_execute=execute_query,
            )
            result = graph.run(query_text, intake_result, shipment_id)

            # ── Done ──────────────────────────────────────────
            push_sse_event(session_id, "result", result)
            mark_session_done(session_id)
            _update_shipment_status(session_id, "completed")

        except Exception as e:
            logger.exception(f"Pipeline error for session {session_id}: {e}")
            push_sse_event(session_id, "error", {"message": str(e)})
            mark_session_done(session_id)
            _update_shipment_status(session_id, "failed")
