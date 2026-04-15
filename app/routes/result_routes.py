"""
app/routes/result_routes.py — GET /result/<session_id>

Blueprint: result_bp
"""
import json

from flask import Blueprint, jsonify

from ..database import execute_query

result_bp = Blueprint("result", __name__)


@result_bp.route("/result/<session_id>")
def get_result(session_id):
    """Get the final result for a completed session."""
    rows = execute_query(
        """
        SELECT s.*, r.risk_score, r.risk_level, r.delay_probability,
               r.factors_json, r.mitigation_json, r.llm_reasoning,
               r.weather_score, r.news_score, r.historical_score,
               r.confidence_score, r.llm_model, r.llm_tokens_used
        FROM shipments s
        LEFT JOIN risk_assessments r ON r.session_id = s.session_id
        WHERE s.session_id = %s
        """,
        (session_id,),
        fetch=True,
    )
    if not rows:
        return jsonify({"error": "session not found"}), 404
    row = rows[0]
    if row.get("created_at"):
        row["created_at"] = row["created_at"].isoformat()
    if row.get("updated_at"):
        row["updated_at"] = row["updated_at"].isoformat()
    if row.get("confidence_score"):
        row["confidence_score"] = float(row["confidence_score"])
    # Parse JSON fields
    for field in ["factors_json", "mitigation_json"]:
        if row.get(field) and isinstance(row[field], str):
            try:
                row[field] = json.loads(row[field])
            except (json.JSONDecodeError, TypeError):
                pass
    # Expose consistent top-level keys (frontend looks for result.factors and result.mitigation)
    if "factors_json" in row:
        row["factors"]    = row["factors_json"] or []
    if "mitigation_json" in row:
        row["mitigation"] = row["mitigation_json"] or []
    return jsonify(row)
