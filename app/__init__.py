"""
app/__init__.py — Flask application factory
"""
from flask import Flask
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .database import init_db_pool, init_schema, close_db
from .models import ref_data


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="../static",
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
            ref_data.load_all(__import__('app.database', fromlist=['execute_query']).execute_query)
            app.logger.info("Reference data cache loaded")
        except Exception as _e:
            app.logger.error(f"Reference data cache failed: {_e}")

    app.teardown_appcontext(close_db)

    # ── Blueprints ────────────────────────────────────────────
    from .routes.main import main_bp
    from .routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
