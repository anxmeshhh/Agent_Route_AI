"""
app/routes/geocode_routes.py — Server-side geocoding proxy

Proxies geocoding requests through Flask to avoid browser CORS issues
with Nominatim. Uses the existing _geocoder.geocode() which checks DB
cache first, then falls back to Nominatim server-side (no CORS).
"""
from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)

geocode_bp = Blueprint("geocode", __name__)


@geocode_bp.route("/geocode", methods=["GET"])
def geocode_proxy():
    """
    GET /api/geocode?q=Mumbai
    Returns: { "lat": 19.076, "lon": 72.877, "display": "Mumbai, ..." }
    """
    place = request.args.get("q", "").strip()
    if not place:
        return jsonify({"error": "Missing 'q' parameter"}), 400

    try:
        from ._geocoder import geocode
        result = geocode(place)
        if result:
            return jsonify(result)
        return jsonify({"error": f"Could not geocode '{place}'"}), 404
    except Exception as e:
        logger.error(f"[geocode-proxy] Error geocoding '{place}': {e}")
        return jsonify({"error": str(e)}), 500
