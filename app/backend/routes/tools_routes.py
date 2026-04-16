"""
app/routes/tools_routes.py — GET /tools

Blueprint: tools_bp
"""
from flask import Blueprint, jsonify, current_app

from app.backend.database import execute_query

tools_bp = Blueprint("tools", __name__)


@tools_bp.route("/tools")
def list_tools():
    """List all registered tools and their schemas."""
    from app.worker.tools.registry import build_tool_registry
    registry = build_tool_registry(execute_query, current_app.config)
    return jsonify(registry.get_schemas_all())

