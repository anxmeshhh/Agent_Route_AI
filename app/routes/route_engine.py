"""
app/routes/route_engine.py — GET /route + GET /route-analysis

Blueprint: route_bp

Uses OSRM real distance for road routes instead of haversine sum.
Adds distance_source and duration_hours metadata to all responses.
"""
import logging

from flask import Blueprint, request, jsonify, current_app

from ._geocoder import geocode, _haversine_km
from ._detect_mode import _detect_transport_mode
from ._road_routing import _osrm_road_route
from ._maritime_routing import _maritime_waypoints
from ._air_routing import _air_route_waypoints
from ._route_enrichment import (
    _enrich_waypoints_with_ai,
    _fetch_dest_weather,
    _compute_alternate_route,
)
from ._route_analysis import (
    _estimate_route_metrics,
    _calculate_cost_impact,
    _optimal_departure_window,
    _suggest_alternative_route,
    _time_saving_actions,
)

logger = logging.getLogger(__name__)
route_bp = Blueprint("route", __name__)


# ─── GET /api/route ──────────────────────────────────────────────
@route_bp.route("/route")
def get_route():
    """
    Real dynamic routing — fully real-time via APIs:
      • Road  → OSRM public API (free, worldwide, real road geometry)
      • Sea   → Intelligent chokepoint-based maritime routing
      • Air   → Great-circle geodesic arc with airport checkpoints
      • Auto  → Detects mode from geography + query params

    Query params:
      origin  string   Place name / city / port
      dest    string   Place name / city / port
      mode    string   'road' | 'sea' | 'air' | 'auto'  (default: 'auto')
    """
    origin = request.args.get("origin", "").strip()
    dest   = request.args.get("dest",   "").strip()
    mode   = request.args.get("mode",   "auto").lower()

    if not origin or not dest:
        return jsonify({"error": "origin and dest are required"}), 400

    try:
        og = geocode(origin)
        dg = geocode(dest)
        if not og or not dg:
            return jsonify({"error": "Could not geocode one or both locations"}), 422

        olat, olon = og["lat"], og["lon"]
        dlat, dlon = dg["lat"], dg["lon"]

        # ── Auto-detect transport mode ────────────────────────────
        if mode == "auto":
            mode = _detect_transport_mode(olat, olon, dlat, dlon, origin, dest)

        # ── Route by mode ─────────────────────────────────────────
        distance_source = "haversine"
        duration_hours = None
        degraded = False

        if mode == "air":
            waypoints = _air_route_waypoints(olat, olon, dlat, dlon, origin, dest)
            is_land   = False
        elif mode == "road":
            road_result = _osrm_road_route(olat, olon, dlat, dlon, origin, dest)
            waypoints = road_result["waypoints"]
            is_land   = True
            degraded  = road_result.get("degraded", False)

            # Use OSRM's actual distance — more accurate than haversine
            if road_result.get("osrm_distance_km"):
                distance_source = road_result.get("source", "osrm_live")
                duration_hours = road_result.get("osrm_duration_hours")
        else:  # sea
            waypoints = _maritime_waypoints(olat, olon, dlat, dlon, origin, dest)
            is_land   = False

        if not waypoints or len(waypoints) < 2:
            return jsonify({"error": f"Could not compute {mode} route between {origin} and {dest}"}), 422

        # ── Distance computation ──────────────────────────────────
        if mode == "road" and not degraded and 'road_result' in dir():
            # Use OSRM's real road distance (accounts for actual road curvature)
            total_km = road_result.get("osrm_distance_km", 0)
            if not total_km:
                total_km = sum(
                    _haversine_km(waypoints[i], waypoints[i + 1])
                    for i in range(len(waypoints) - 1)
                )
                distance_source = "haversine"
        else:
            total_km = sum(
                _haversine_km(waypoints[i], waypoints[i + 1])
                for i in range(len(waypoints) - 1)
            )

        # ── Enrich waypoints with AI reasoning ────────────────────
        waypoints = _enrich_waypoints_with_ai(waypoints, origin, dest, mode, total_km)

        # ── Fetch real weather for destination ────────────────────
        dest_weather = _fetch_dest_weather(dest, dlat, dlon)

        # ── Compute alternate route for ALL modes ─────────────────
        alt_route = _compute_alternate_route(
            olat, olon, dlat, dlon, origin, dest, waypoints, mode, total_km,
            duration_hours
        )

        response = {
            "origin":          {**og, "name": origin},
            "dest":            {**dg, "name": dest},
            "waypoints":       waypoints,
            "route_type":      waypoints[0].get("via", mode),
            "is_land_route":   is_land,
            "transport_mode":  mode,
            "total_km":        round(total_km),
            "distance_source": distance_source,
            "degraded":        degraded,
        }
        if duration_hours is not None:
            response["duration_hours"] = duration_hours
        if dest_weather:
            response["dest_weather"] = dest_weather
        if alt_route:
            response["alternate_route"] = alt_route
        return jsonify(response)
    except Exception as e:
        logger.exception(f"[route] Error: {e}")
        return jsonify({"error": str(e)}), 500


# ─── GET /api/route-analysis ─────────────────────────────────────
@route_bp.route("/route-analysis")
def route_analysis():
    """
    Advanced predictive intelligence for a route:
      - Real-time OSRM distance and transit time
      - Delay cost impact (USD) based on risk score
      - Time-saving recommendation: depart earlier / wait / proceed
      - Alternative safe route if primary route is HIGH risk
      - Optimal departure window (best day in next 7 days)
    """
    origin    = request.args.get("origin", "").strip()
    dest      = request.args.get("dest",   "").strip()
    cargo_type = request.args.get("cargo_type", "general").lower()

    # Safe int parsing — frontend may pass '--' for unknown values
    try:
        risk_score = int(request.args.get("risk_score", 30))
    except (ValueError, TypeError):
        risk_score = 30
    try:
        eta_days = int(request.args.get("eta_days", 14))
    except (ValueError, TypeError):
        eta_days = 14

    if not origin or not dest:
        return jsonify({"error": "origin and dest required"}), 400

    try:
        # ── Detect transport mode ──────────────────────────────────────
        transport_mode = request.args.get("transport_mode", "auto").lower()
        if transport_mode == "auto":
            og = geocode(origin)
            dg = geocode(dest)
            if og and dg:
                transport_mode = _detect_transport_mode(
                    og["lat"], og["lon"], dg["lat"], dg["lon"], origin, dest
                )
            else:
                transport_mode = "sea"

        # ── 1. Route Distance Estimation (real-time OSRM) ────────────
        route_info = _estimate_route_metrics(origin, dest)
        route_info["transport_mode"] = transport_mode

        # ── 2. Delay Cost Impact Modelling (mode-aware) ──────────────
        cost_data = _calculate_cost_impact(risk_score, cargo_type, eta_days,
                                            route_info, transport_mode)

        # ── 3. Optimal Departure Recommendation (real OWM 5-day forecast) ──
        owm_key   = current_app.config.get("OPENWEATHER_API_KEY", "")
        port_city = request.args.get("port_city", dest).strip()
        departure = _optimal_departure_window(risk_score, eta_days, port_city, owm_key)

        # ── 4. Alternative Route (ALWAYS compute for comparison) ─────
        alt_route = _suggest_alternative_route(origin, dest, route_info["via"],
                                               transport_mode, route_info)

        # ── 5. Time-Saving Actions ────────────────────────────────────
        savings = _time_saving_actions(risk_score, eta_days, cargo_type, cost_data)

        return jsonify({
            "route": route_info,
            "cost_impact": cost_data,
            "departure_window": departure,
            "alternative_route": alt_route,
            "time_savings": savings,
        })
    except Exception as e:
        logger.exception(f"[route-analysis] Error: {e}")
        return jsonify({"error": str(e)}), 500
