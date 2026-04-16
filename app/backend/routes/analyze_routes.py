"""
app/routes/analyze_routes.py — POST /analyze endpoint + background pipeline

Blueprint: analyze_bp

Accepts BOTH modes:
  1. Structured form (USER role): origin, dest, cargo_type, weight_kg, budget_usd,
     eta_days, shipment_uuid — builds the NLP query automatically, bypasses NLP.
  2. Free-text query (legacy / admin): query field only.
"""
import re as _re
import uuid
import time
import logging
import threading

from flask import Blueprint, request, jsonify, current_app, g

from app.worker.agents.intake_agent import IntakeAgent
from app.backend.database import execute_query
from ._sse import push_sse_event, mark_session_done, init_sse_session
from ._db_helpers import _store_shipment, _update_shipment_status, _log_to_db
from ..auth.decorators import login_required

logger = logging.getLogger(__name__)
analyze_bp = Blueprint("analyze", __name__)

_CARGO_OPTIONS = [
    "general", "electronics", "perishables", "pharmaceuticals",
    "automotive", "chemicals", "bulk", "energy",
]


@analyze_bp.route("/analyze", methods=["POST"])
@login_required
def analyze():
    """
    Start an analysis run using the agentic graph. Requires valid JWT.

    Accepts JSON with either:
      Structured mode: { origin, destination, cargo_type, weight_kg,
                         budget_usd, eta_days, shipment_uuid? }
      Free-text mode:  { query }
    """
    body = request.get_json(silent=True) or {}

    # Capture identity from JWT (set by @login_required in g)
    org_id  = getattr(g, "org_id",  1)
    user_id = getattr(g, "user_id", None)

    # ── Structured form mode (USER role) ──────────────────────
    origin      = (body.get("origin")      or "").strip()
    destination = (body.get("destination") or "").strip()
    cargo_type  = (body.get("cargo_type")  or "general").strip().lower()
    weight_kg   = body.get("weight_kg")
    budget_usd  = body.get("budget_usd")
    eta_days_raw = body.get("eta_days")
    ship_uuid   = (body.get("shipment_uuid") or "").strip()
    query_text  = (body.get("query")       or "").strip()

    if cargo_type not in _CARGO_OPTIONS:
        cargo_type = "general"

    # If structured fields provided, synthesize the NLP query for the agents
    if origin and destination:
        parts = [f"{cargo_type} cargo from {origin} to {destination}"]
        if eta_days_raw:
            parts.append(f"in {int(eta_days_raw)} days")
        if weight_kg:
            parts.append(f"weight {float(weight_kg)} kg")
        if budget_usd:
            parts.append(f"budget USD {float(budget_usd)}")
        query_text = " ".join(parts)

    # ── Input validation ──────────────────────────────────────
    if not query_text:
        return jsonify({"error": "Provide origin + destination, or a free-text query"}), 400
    if len(query_text) > 1000:
        return jsonify({"error": "query too long (max 1000 chars)"}), 400
    if len(query_text) < 5:
        return jsonify({"error": "query too short — describe a shipment"}), 400

    query_text = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', query_text)

    # Generate or validate shipment UUID
    if not ship_uuid:
        ship_uuid = str(uuid.uuid4())[:8].upper()  # short 8-char friendly UUID
    elif len(ship_uuid) > 36:
        return jsonify({"error": "shipment_uuid too long (max 36 chars)"}), 400

    session_id = str(uuid.uuid4())
    init_sse_session(session_id)

    # Structured pre-parsed data to pass to intake agent (skips NLP)
    structured = {}
    if origin and destination:
        structured = {
            "origin_port":    origin,
            "port":           destination,
            "port_city":      destination,
            "cargo_type":     cargo_type,
            "eta_days":       int(eta_days_raw) if eta_days_raw else None,
            "shipment_uuid":  ship_uuid,
            "budget_usd":     float(budget_usd) if budget_usd else None,
            "weight_kg":      float(weight_kg)  if weight_kg  else None,
        }

    app = current_app._get_current_object()
    thread = threading.Thread(
        target=_run_analysis_pipeline,
        args=(app, session_id, query_text, org_id, user_id, structured),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "session_id":    session_id,
        "shipment_uuid": ship_uuid,
        "status":        "running",
        "stream_url":    f"/api/stream/{session_id}",
    })


def _run_analysis_pipeline(app, session_id: str, query_text: str,
                            org_id: int = 1, user_id: int = None,
                            structured: dict = None):
    """
    Runs the full agentic graph in a background thread.
    1. Intake Agent parses the query (or accepts pre-parsed structured data)
    2. AgentGraph orchestrates all agents via LLM-based routing
    3. Results stream to UI via SSE
    """
    with app.app_context():
        try:
            push_sse_event(session_id, "agent_log", {
                "agent":  "intake",
                "action": "🤖 Intake Agent — parsing your shipment query...",
                "status": "started",
            })

            intake = IntakeAgent()
            intake_result = intake.run(query_text, session_id,
                                       structured_override=structured or {})

            for log in intake_result.get("logs", []):
                push_sse_event(session_id, "agent_log", {
                    "agent":  log["agent"],
                    "action": log["action"],
                    "status": log["status"],
                    "data":   log.get("data"),
                })
                time.sleep(0.04)

            push_sse_event(session_id, "agent_log", {
                "agent":  "intake",
                "action": "Persisting shipment to MySQL...",
                "status": "started",
            })

            shipment_id = _store_shipment(session_id, intake_result, org_id, user_id)
            _log_to_db(session_id, "intake", "Shipment stored in database",
                       "success", {"shipment_id": shipment_id})

            push_sse_event(session_id, "agent_log", {
                "agent":  "intake",
                "action": f"Shipment stored (UUID: {intake_result.get('shipment_uuid', session_id[:8])})",
                "status": "success",
            })

            push_sse_event(session_id, "agent_log", {
                "agent":  "graph",
                "action": "🧠 Agentic Graph — LLM Router deciding agent sequence...",
                "status": "started",
            })
            from app.worker.agents.graph import AgentGraph
            graph = AgentGraph(
                session_id=session_id,
                push_event=push_sse_event,
                config=app.config,
                db_execute=execute_query,
            )
            result = graph.run(query_text, intake_result, shipment_id)

            push_sse_event(session_id, "result", result)
            mark_session_done(session_id)
            _update_shipment_status(session_id, "completed")

        except Exception as e:
            logger.exception(f"Pipeline error for session {session_id}: {e}")
            push_sse_event(session_id, "error", {"message": str(e)})
            mark_session_done(session_id)
            _update_shipment_status(session_id, "failed")

