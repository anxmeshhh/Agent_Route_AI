"""
app/routes/main.py — Dashboard + Auth page routes
"""
from flask import Blueprint, render_template, redirect, url_for, make_response
from app.backend.config import Config

main_bp = Blueprint("main", __name__)


@main_bp.route("/favicon.ico")
def favicon():
    """Suppress favicon 404 — return empty 204 No Content."""
    return make_response("", 204)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/login")
def login_page():
    return render_template("login.html")


@main_bp.route("/signup")
def signup_page():
    return render_template("signup.html")


@main_bp.route("/otp")
def otp_page():
    return render_template("otp.html")


@main_bp.route("/logs")
def logs_page():
    return render_template("logs.html")


@main_bp.route("/analysis")
def analysis_page():
    return render_template("analysis.html", google_maps_key=Config.GOOGLE_MAPS_API_KEY)


@main_bp.route("/admin")
def admin_page():
    return render_template("admin.html")


@main_bp.route("/health")
def health():
    return {"status": "ok", "service": "Predictive Delay & Risk Intelligence Agent"}

