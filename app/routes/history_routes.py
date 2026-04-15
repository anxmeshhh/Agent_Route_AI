"""
app/routes/history_routes.py — GET /history

Blueprint: history_bp
"""
from flask import Blueprint, jsonify

from ..database import execute_query

history_bp = Blueprint("history", __name__)


@history_bp.route("/history")
def history():
    """Return the last 20 completed analyses."""
    rows = execute_query(
        """
        SELECT s.session_id, s.query_text, s.port, s.eta_days, s.cargo_type,
               s.status, s.created_at,
               r.risk_score, r.risk_level, r.delay_probability,
               r.confidence_score
        FROM shipments s
        LEFT JOIN risk_assessments r ON r.session_id = s.session_id
        ORDER BY s.created_at DESC
        LIMIT 20
        """,
        fetch=True,
    )
    for row in rows:
        if row.get("created_at"):
            row["created_at"] = row["created_at"].isoformat()
        if row.get("confidence_score"):
            row["confidence_score"] = float(row["confidence_score"])
    return jsonify(rows)
