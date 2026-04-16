"""
app/routes/history_routes.py — GET /history

Returns analyses scoped to the current user's organisation.
If the user has approved visibility into other orgs, those are
also included (tagged with org_name for UI display).

Blueprint: history_bp
"""
from flask import Blueprint, jsonify, g

from ..database import execute_query
from ..auth.decorators import login_required

history_bp = Blueprint("history", __name__)


@history_bp.route("/history")
@login_required
def history():
    """
    Return the last 20 completed analyses for:
      1. The current user's org
      2. Any orgs that this org has approved visibility into
    """
    org_id = g.org_id

    # Find approved visible org IDs
    approved = execute_query(
        """SELECT target_org_id FROM org_visibility_requests
           WHERE requester_org_id=%s AND status='approved'""",
        (org_id,), fetch=True
    )
    visible_org_ids = [org_id] + [r["target_org_id"] for r in approved]

    # Build IN clause safely
    placeholders = ",".join(["%s"] * len(visible_org_ids))

    rows = execute_query(
        f"""
        SELECT s.session_id, s.query_text, s.port, s.eta_days, s.cargo_type,
               s.status, s.created_at, s.org_id,
               o.name AS org_name,
               r.risk_score, r.risk_level, r.delay_probability,
               r.confidence_score
        FROM shipments s
        LEFT JOIN risk_assessments r ON r.session_id = s.session_id
        LEFT JOIN organisations o ON o.id = s.org_id
        WHERE s.org_id IN ({placeholders})
        ORDER BY s.created_at DESC
        LIMIT 25
        """,
        tuple(visible_org_ids),
        fetch=True,
    )

    for row in rows:
        if row.get("created_at"):
            row["created_at"] = row["created_at"].isoformat()
        if row.get("confidence_score") is not None:
            row["confidence_score"] = float(row["confidence_score"])
        if row.get("delay_probability") is not None:
            row["delay_probability"] = float(row["delay_probability"])
        # Flag cross-org entries for UI treatment
        row["is_own_org"] = (row.get("org_id") == org_id)

    return jsonify(rows)
