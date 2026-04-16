"""
app/__init__.py — Flask application factory
"""
from flask import Flask
from flask_cors import CORS

from .config import Config
from .database import init_db_pool, init_schema, close_db


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="../static",
        static_url_path="/static",
    )
    app.config.from_object(Config)

    # CORS for streaming + cookie-based auth
    CORS(app, supports_credentials=True)

    # Database
    with app.app_context():
        init_schema(app)
        init_db_pool(app)

    app.teardown_appcontext(close_db)

    # ── Blueprints ────────────────────────────────────────────
    from .routes.main import main_bp
    from .routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
