"""
app/routes/api.py — Thin aggregator Blueprint

All API endpoints are implemented in dedicated route modules.
This file creates the parent `api_bp` Blueprint and registers
every child Blueprint onto it.

The public import path remains:
    from .routes.api import api_bp

so app/__init__.py needs ZERO changes.

Endpoints (all under /api prefix):
  POST /api/analyze          — analyze_routes
  GET  /api/stream/<sid>     — stream_routes
  GET  /api/history          — history_routes
  GET  /api/result/<sid>     — result_routes
  GET  /api/logs/<sid>       — logs_routes
  GET  /api/analytics        — analytics_routes
  POST /api/feedback         — feedback_routes
  GET  /api/tools            — tools_routes
  GET  /api/route            — route_engine
  GET  /api/route-analysis   — route_engine
"""
from flask import Blueprint

# ── Parent Blueprint ──────────────────────────────────────────────
api_bp = Blueprint("api", __name__)

# ── Import child Blueprints ───────────────────────────────────────
from .analyze_routes import analyze_bp
from .stream_routes import stream_bp
from .history_routes import history_bp
from .result_routes import result_bp
from .logs_routes import logs_bp
from .analytics_routes import analytics_bp
from .feedback_routes import feedback_bp
from .tools_routes import tools_bp
from .route_engine import route_bp

# ── Register children onto api_bp ─────────────────────────────────
api_bp.register_blueprint(analyze_bp)
api_bp.register_blueprint(stream_bp)
api_bp.register_blueprint(history_bp)
api_bp.register_blueprint(result_bp)
api_bp.register_blueprint(logs_bp)
api_bp.register_blueprint(analytics_bp)
api_bp.register_blueprint(feedback_bp)
api_bp.register_blueprint(tools_bp)
api_bp.register_blueprint(route_bp)
