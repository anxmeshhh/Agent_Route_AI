"""
app/routes/feedback_routes.py — POST /feedback

Blueprint: feedback_bp
"""
from flask import Blueprint, request, jsonify, current_app

from app.backend.database import execute_query

feedback_bp = Blueprint("feedback", __name__)


@feedback_bp.route("/feedback", methods=["POST"])
def feedback():
    """Record actual outcome for a prediction (learning loop)."""
    body = request.get_json(silent=True) or {}
    session_id = body.get("session_id")
    delay_days = body.get("actual_delay_days")
    issues = body.get("actual_issues")

    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    from app.worker.agents.memory import MemoryAgent
    memory = MemoryAgent(execute_query, current_app.config)
    memory.record_outcome(session_id, delay_days, issues)

    return jsonify({"status": "ok", "message": "Outcome recorded — thank you for the feedback"})

