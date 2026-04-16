"""
app/routes/analytics_routes.py — GET /analytics

Blueprint: analytics_bp
"""
from flask import Blueprint, jsonify, current_app

from app.backend.database import execute_query

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/analytics")
def analytics():
    """System-wide analytics for the dashboard."""
    from app.worker.agents.memory import MemoryAgent
    memory = MemoryAgent(execute_query, current_app.config)
    return jsonify(memory.get_analytics())

