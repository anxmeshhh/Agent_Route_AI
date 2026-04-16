"""
app/__init__.py — Flask application factory
"""
import os
from flask import Flask
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from app.backend.config import Config
from app.backend.database import init_db_pool, init_schema, close_db
from app.backend.models import ref_data


def create_app():
    # Resolve absolute paths to frontend assets
    _here = os.path.dirname(os.path.abspath(__file__))
    _tmpl = os.path.join(_here, "frontend", "templates")
    _static = os.path.join(_here, "frontend", "static")

    app = Flask(
        __name__,
        template_folder=_tmpl,
        static_folder=_static,
        static_url_path="/static",
    )
    app.config.from_object(Config)

    # Trust 1 level of reverse proxy (ngrok / nginx / etc.)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # CORS for streaming + cookie-based auth
    CORS(app, supports_credentials=True)

    # Database — order matters: pool first, then schema, then ref cache
    with app.app_context():
        init_db_pool(app)
        init_schema(app)
        # Load all reference tables into memory after pool + schema are ready
        try:
            from app.backend.database import execute_query as _eq
            ref_data.load_all(_eq)
            app.logger.info("Reference data cache loaded")
        except Exception as _e:
            app.logger.error(f"Reference data cache failed: {_e}")

    app.teardown_appcontext(close_db)

    # ── Blueprints ────────────────────────────────────────────
    from app.backend.routes.main import main_bp
    from app.backend.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # ── JSON error handlers — never return HTML for API routes ────
    from flask import jsonify as _jf, request as _req
    import traceback as _tb

    @app.errorhandler(400)
    def _e400(e):
        if _req.path.startswith("/api"):
            return _jf({"error": str(e.description) if hasattr(e, "description") else "Bad request"}), 400
        return e

    @app.errorhandler(404)
    def _e404(e):
        if _req.path.startswith("/api"):
            return _jf({"error": "Not found"}), 404
        return e

    @app.errorhandler(405)
    def _e405(e):
        if _req.path.startswith("/api"):
            return _jf({"error": "Method not allowed"}), 405
        return e

    @app.errorhandler(500)
    def _e500(e):
        if _req.path.startswith("/api"):
            app.logger.error(f"API 500: {_req.method} {_req.path} — {e}\n{_tb.format_exc()}")
            return _jf({"error": f"Internal server error: {str(e)}"}), 500
        return e

    @app.errorhandler(Exception)
    def _unhandled(e):
        if _req.path.startswith("/api"):
            app.logger.error(f"Unhandled: {_req.method} {_req.path} — {e}\n{_tb.format_exc()}")
            return _jf({"error": f"Server error: {str(e)}"}), 500
        raise e

    return app

