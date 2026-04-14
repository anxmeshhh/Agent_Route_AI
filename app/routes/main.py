"""
app/routes/main.py — Dashboard routes
"""
from flask import Blueprint, render_template
from app.config import Config

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html", google_maps_key=Config.GOOGLE_MAPS_API_KEY)


@main_bp.route("/health")
def health():
    return {"status": "ok", "service": "Predictive Delay & Risk Intelligence Agent"}
