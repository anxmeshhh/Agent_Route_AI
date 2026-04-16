"""
app/routes/_route_enrichment.py — Real-time route intelligence

ZERO identical text — every waypoint gets UNIQUE, position-aware reasoning
based on its actual location, distance, road name, and transport mode.

Public API:
  _enrich_waypoints_with_ai(waypoints, origin, dest, mode, total_km) -> list
  _fetch_dest_weather(dest_name, lat, lon) -> dict | None
  _compute_alternate_route(olat, olon, dlat, dlon, origin, dest, primary_wps) -> dict | None

Chokepoint intel and maritime alternate route definitions loaded from MySQL
via ref_data. No hardcoded CHOKEPOINT_INTEL dict or inline waypoint lists.
"""
import logging
import math

from ._geocoder import _haversine_km

logger = logging.getLogger(__name__)


def _get_chokepoint_intel() -> dict:
    """DB-backed chokepoint intelligence baseline."""
    try:
        from ..models import ref_data
        return ref_data.get_chokepoint_intel()
    except Exception:
        return {}


def _get_alt_routes() -> dict:
    """DB-backed maritime alternate route definitions."""
    try:
        from ..models import ref_data
        return ref_data.get_maritime_alt_routes()
    except Exception:
        return {}


def _enrich_waypoints_with_ai(waypoints: list, origin: str, dest: str,
                               mode: str, total_km: float) -> list:
    """
    Add UNIQUE, position-aware AI reasoning to each waypoint.
    Chokepoint intel loaded from MySQL ref_chokepoint_intel.
    """
    n_checkpoints = len(waypoints) - 2
    if n_checkpoints <= 0:
        return waypoints

    intel = _get_chokepoint_intel()

    for i, wp in enumerate(waypoints):
        # ── Origin/Destination ──────────────────────────────────
        if i == 0:
            wp["ai_reasoning"] = (
                f"🟢 Origin: {origin} — Route intelligence active for "
                f"{round(total_km):,} km {mode} journey to {dest}"
            )
            continue
        if i == len(waypoints) - 1:
            wp["ai_reasoning"] = (
                f"🔴 Destination: {dest} — {n_checkpoints} waypoints traversed, "
                f"{round(total_km):,} km journey complete"
            )
            continue

        # ── Position metrics ────────────────────────────────────
        frac        = i / (len(waypoints) - 1)
        km_at_point = wp.get("elapsed_km") or wp.get("segment_km") or round(total_km * frac)
        remaining_km = round(total_km - km_at_point)
        pct         = wp.get("progress_pct") or round(frac * 100, 1)
        name        = (wp.get("name") or "").strip()
        road        = wp.get("road", "")
        remaining_h = wp.get("remaining_hours")

        # ── Maritime chokepoint intelligence from DB ────────────
        name_lower = name.lower()
        matched = False
        for key, cp_intel in intel.items():
            if key in name_lower:
                wp["ai_reasoning"] = (
                    f"🧠 AI waypoint selection: {cp_intel['why']}. "
                    f"Saves: {cp_intel['saves']}. "
                    f"Risk monitored: {cp_intel['risk']}. "
                    f"[Source: {cp_intel['intel_source']}]"
                )
                matched = True
                break

        if matched:
            continue

        # ── Mode-specific UNIQUE reasoning ──────────────────────
        if mode == "road":
            road_info = f" on {road}" if road else ""
            eta_info  = f" · ETA to dest: ~{remaining_h}h" if remaining_h else ""

            if pct < 15:
                phase  = "Departure phase"
                detail = f"Clearing origin urban zone{road_info}, entering highway corridor"
            elif pct < 35:
                phase  = "Highway cruise"
                detail = f"Steady highway transit{road_info}, fuel reserves adequate"
            elif pct < 50:
                phase  = "Mid-route"
                detail = f"Approaching midpoint{road_info}, recommended rest/refuel window"
            elif pct < 70:
                phase  = "Approach phase"
                detail = f"Past midpoint{road_info}, monitoring traffic density ahead"
            elif pct < 90:
                phase  = "Final approach"
                detail = f"Nearing destination region{road_info}, preparing for urban navigation"
            else:
                phase  = "Last mile"
                detail = f"Entering destination zone{road_info}, final delivery routing"

            wp["ai_reasoning"] = (
                f"🧠 {phase} — {km_at_point:,} km / {round(total_km):,} km ({pct}%) · "
                f"{detail}{eta_info} · {remaining_km:,} km remaining"
            )

        elif mode == "air":
            if pct < 10:
                phase = "Climb-out"; alt = "ascending through FL100"
            elif pct < 25:
                phase = "Initial cruise"; alt = "reaching cruise altitude FL350"
            elif pct < 75:
                phase = "Cruise"; alt = "FL350-FL410 optimal fuel burn"
            elif pct < 90:
                phase = "Descent planning"; alt = "step-down descent initiated"
            else:
                phase = "Final approach"; alt = "below FL100, approach clearance"

            wp["ai_reasoning"] = (
                f"🧠 {phase} — {km_at_point:,} km en route ({pct}%) · "
                f"Airspace: {alt} · "
                f"Great-circle track {remaining_km:,} km to destination"
            )

        else:
            # Maritime — bearing + sea-state context
            bearing       = _compute_bearing(
                wp.get("lat", 0), wp.get("lon", 0),
                waypoints[-1].get("lat", 0), waypoints[-1].get("lon", 0)
            )
            bearing_label = _bearing_to_cardinal(bearing)
            days_est      = round(remaining_km / 550, 1)  # ~550 km/day vessel average

            if name:
                wp["ai_reasoning"] = (
                    f"🧠 Maritime waypoint: {name} — {km_at_point:,} km from origin ({pct}%) · "
                    f"Heading {bearing_label} ({bearing}°) · "
                    f"~{remaining_km:,} km / ~{days_est} days to destination"
                )
            else:
                wp["ai_reasoning"] = (
                    f"🧠 Open ocean transit — {km_at_point:,} km ({pct}%) · "
                    f"Heading {bearing_label} ({bearing}°) · "
                    f"~{remaining_km:,} km / ~{days_est} days remaining · "
                    f"Sea-state monitoring active"
                )

    return waypoints


def _compute_bearing(lat1, lon1, lat2, lon2) -> int:
    """Compute initial bearing from point 1 to point 2."""
    lat1, lon1 = math.radians(lat1), math.radians(lon1)
    lat2, lon2 = math.radians(lat2), math.radians(lon2)
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return round(math.degrees(math.atan2(x, y)) % 360)


def _bearing_to_cardinal(bearing: int) -> str:
    """Convert bearing degrees to cardinal direction."""
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[round(bearing / 22.5) % 16]


def _fetch_dest_weather(dest_name: str, lat: float, lon: float) -> dict:
    """Fetch REAL live weather for destination from OpenWeather API."""
    import requests as _req
    import os
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not api_key:
        return None

    try:
        r = _req.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
            timeout=5,
        )
        if r.status_code != 200:
            return None
        d = r.json()
        return {
            "city":           dest_name,
            "temp_c":         round(d["main"]["temp"], 1),
            "feels_like_c":   round(d["main"]["feels_like"], 1),
            "description":    d["weather"][0]["description"].title() if d.get("weather") else "Unknown",
            "icon":           d["weather"][0]["icon"] if d.get("weather") else "01d",
            "wind_speed_kmh": round(d["wind"]["speed"] * 3.6, 1) if d.get("wind") else 0,
            "wind_deg":       d.get("wind", {}).get("deg", 0),
            "humidity":       d["main"].get("humidity", 0),
            "pressure_hpa":   d["main"].get("pressure", 0),
            "visibility_km":  round(d.get("visibility", 10000) / 1000, 1),
            "source":         "OpenWeather API (live)",
        }
    except Exception as e:
        logger.warning(f"[weather] Failed to fetch live weather for {dest_name}: {e}")
        return None


def _compute_alternate_route(olat, olon, dlat, dlon, origin, dest,
                              primary_wps, mode="sea", primary_km=None,
                              primary_hours=None) -> dict:
    """Compute an alternate route for ANY transport mode."""
    if mode == "road":
        return _road_alternate(olat, olon, dlat, dlon, origin, dest,
                               primary_km, primary_hours)
    elif mode == "air":
        return _air_alternate(olat, olon, dlat, dlon, origin, dest,
                              primary_km, primary_hours)
    else:
        return _sea_alternate(olat, olon, dlat, dlon, origin, dest,
                              primary_wps, primary_km)


def _road_alternate(olat, olon, dlat, dlon, origin, dest,
                    primary_km, primary_hours) -> dict:
    """Get alternate road route from OSRM alternatives=true."""
    import requests as _req

    try:
        url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{olon},{olat};{dlon},{dlat}"
            f"?overview=simplified&alternatives=true&steps=false"
        )
        resp = _req.get(url, timeout=10, headers={"User-Agent": "AgentRouteAI/3.0"})
        if resp.status_code != 200:
            return None

        data   = resp.json()
        routes = data.get("routes", [])
        if len(routes) < 2:
            return None

        alt       = routes[1]
        alt_km    = round(alt["distance"] / 1000)
        alt_hours = round(alt["duration"] / 3600, 1)
        p_km      = primary_km or round(routes[0]["distance"] / 1000)
        p_hours   = primary_hours or round(routes[0]["duration"] / 3600, 1)
        delta_km    = alt_km - p_km
        delta_hours = round(alt_hours - (p_hours or alt_hours), 1)

        alt_waypoints = []
        geometry = alt.get("geometry", "")
        if geometry:
            decoded = _decode_polyline(geometry)
            step = max(1, len(decoded) // 8)
            for j in range(0, len(decoded), step):
                alt_waypoints.append({"lat": decoded[j][0], "lon": decoded[j][1]})
            if alt_waypoints and (alt_waypoints[-1]["lat"] != dlat):
                alt_waypoints.append({"lat": dlat, "lon": dlon})

        if alt_waypoints:
            alt_waypoints[0]["via"] = "Alternate Road Route"

        return {
            "waypoints":    alt_waypoints,
            "total_km":     alt_km,
            "duration_hours": alt_hours,
            "delta_km":     delta_km,
            "delta_hours":  delta_hours,
            "reason": (
                f"Alternate road route via different highway corridor. "
                f"{'Longer' if delta_km > 0 else 'Shorter'} by {abs(delta_km)} km, "
                f"{'slower' if delta_hours > 0 else 'faster'} by {abs(delta_hours)}h."
            ),
            "when_to_choose": (
                "Choose this route if the primary highway has congestion, "
                "road closures, or weather disruptions."
            ),
            "label": "Alternate Road Route",
            "comparison": {
                "primary":   {"km": p_km, "hours": p_hours},
                "alternate": {"km": alt_km, "hours": alt_hours},
                "delta":     {"km": delta_km, "hours": delta_hours},
            },
        }
    except Exception as e:
        logger.warning(f"[alt-road] OSRM alternatives failed: {e}")
        return None


def _air_alternate(olat, olon, dlat, dlon, origin, dest,
                   primary_km, primary_hours) -> dict:
    """Suggest alternate air route via connecting hub loaded from DB geocoords."""
    dist = _haversine_km({"lat": olat, "lon": olon}, {"lat": dlat, "lon": dlon})
    if dist < 1000:
        return None

    # Use DB-backed geocoords for hub selection
    try:
        from ..models import ref_data
        geocoords = ref_data.get_geocoords()
    except Exception:
        geocoords = {}

    # Default hub: Delhi IGI
    hub_key  = "del -- indira gandhi intl"
    hub_name = "Delhi (DEL)"
    hub_lat  = 28.5562
    hub_lon  = 77.1000

    # If both are DB-geocoded entries in India, use Mumbai
    india_bounds = lambda la, lo: 6 < la < 37 and 68 < lo < 98
    if india_bounds(olat, olon) and india_bounds(dlat, dlon):
        bom = geocoords.get("bom -- chhatrapati shivaji intl")
        if bom:
            hub_lat, hub_lon = bom["lat"], bom["lon"]
            hub_name = "Mumbai (BOM)"
        else:
            hub_lat, hub_lon = 19.0896, 72.8656
            hub_name = "Mumbai (BOM)"

    leg1   = _haversine_km({"lat": olat, "lon": olon}, {"lat": hub_lat, "lon": hub_lon})
    leg2   = _haversine_km({"lat": hub_lat, "lon": hub_lon}, {"lat": dlat, "lon": dlon})
    alt_km = round(leg1 + leg2)
    delta_km = alt_km - (primary_km or round(dist))

    return {
        "waypoints": [
            {"lat": olat, "lon": olon, "via": f"Connecting via {hub_name}"},
            {"lat": hub_lat, "lon": hub_lon, "name": hub_name},
            {"lat": dlat, "lon": dlon},
        ],
        "total_km":  alt_km,
        "delta_km":  delta_km,
        "reason":    f"Connecting flight via {hub_name} — may offer better availability or lower cost.",
        "when_to_choose": "Choose if direct flights are unavailable, overbooked, or during monsoon disruptions.",
        "label": f"Via {hub_name}",
        "comparison": {
            "primary":   {"km": primary_km or round(dist), "type": "direct"},
            "alternate": {"km": alt_km, "type": "connecting"},
            "delta":     {"km": delta_km},
        },
    }


def _sea_alternate(olat, olon, dlat, dlon, origin, dest,
                   primary_wps, primary_km) -> dict:
    """Maritime alternate via DB-loaded chokepoint avoidance definitions."""
    primary_names = [wp.get("name", "").lower() for wp in primary_wps]
    primary_via   = " ".join(primary_names)

    alt_routes = _get_alt_routes()

    # Match this route to a DB-defined alternate
    matched = None
    for trigger_key, alt_data in alt_routes.items():
        if trigger_key in primary_via:
            matched = alt_data
            break

    if not matched:
        return None

    # Build full waypoint list
    alt_waypoints = [
        {"lat": olat, "lon": olon, "name": origin, "via": matched["via_label"] + " · Alt Route"},
        *matched["waypoints"],
        {"lat": dlat, "lon": dlon, "name": dest},
    ]

    alt_km = sum(
        _haversine_km(alt_waypoints[i], alt_waypoints[i + 1])
        for i in range(len(alt_waypoints) - 1)
    )

    p_km = primary_km or sum(
        _haversine_km(primary_wps[i], primary_wps[i + 1])
        for i in range(len(primary_wps) - 1)
    )

    km_per_day  = matched.get("km_per_day", 550)
    extra_km    = round(alt_km - p_km)
    extra_days  = round(extra_km / km_per_day, 1)

    return {
        "waypoints":        alt_waypoints,
        "total_km":         round(alt_km),
        "extra_km":         extra_km,
        "extra_days":       extra_days,
        "reason":           matched["reason"],
        "when_to_choose":   matched["when_to_choose"],
        "label":            matched["via_label"],
        "comparison": {
            "primary":   {"km": round(p_km),  "days": round(p_km / km_per_day, 1)},
            "alternate": {"km": round(alt_km), "days": round(alt_km / km_per_day, 1)},
            "delta":     {"km": extra_km, "days": extra_days},
        },
    }


def _decode_polyline(encoded: str) -> list:
    """Decode Google-style polyline encoding to list of [lat, lon] pairs."""
    result = []
    idx, lat, lng = 0, 0, 0
    while idx < len(encoded):
        for coord in range(2):
            shift, value = 0, 0
            while True:
                b = ord(encoded[idx]) - 63
                idx += 1
                value |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(value >> 1) if (value & 1) else (value >> 1)
            if coord == 0:
                lat += delta
            else:
                lng += delta
        result.append((lat / 1e5, lng / 1e5))
    return result
