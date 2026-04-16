"""
app/routes/main.py — Dashboard + Auth page routes
"""
from flask import Blueprint, render_template, redirect, url_for
from app.config import Config

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html", google_maps_key=Config.GOOGLE_MAPS_API_KEY)


@main_bp.route("/login")
def login_page():
    return render_template("login.html")


@main_bp.route("/signup")
def signup_page():
    return render_template("signup.html")


@main_bp.route("/otp")
def otp_page():
    return render_template("otp.html")


@main_bp.route("/health")
def health():
    return {"status": "ok", "service": "Predictive Delay & Risk Intelligence Agent"}
