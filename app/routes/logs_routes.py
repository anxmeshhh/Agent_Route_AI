"""
app/routes/logs_routes.py — GET /logs/<session_id>

Blueprint: logs_bp
"""
from flask import Blueprint, jsonify

from ..database import execute_query

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/logs/<session_id>")
def get_logs(session_id):
    """Get all agent logs for a session (for replaying analysis)."""
    rows = execute_query(
        """
        SELECT agent_name, action, status, message, data_json, duration_ms, created_at
        FROM agent_logs
        WHERE session_id = %s
        ORDER BY created_at ASC
        """,
        (session_id,),
        fetch=True,
    )
    for row in rows:
        if row.get("created_at"):
            row["created_at"] = row["created_at"].isoformat()
    return jsonify(rows)
