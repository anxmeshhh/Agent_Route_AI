"""
app/routes/_road_routing.py — Production OSRM road routing

All routing is REAL-TIME via OSRM public API:
  - Full road geometry with step-by-step instructions
  - Real road names and highway numbers from OSRM steps
  - Actual distance (km) and duration (hours) from OSRM
  - Named checkpoint snapping for major hubs (from MySQL ref_geocoords)
  - SLERP geodesic fallback (clearly marked as degraded)

Public API:
  _osrm_road_route(olat, olon, dlat, dlon, origin_name, dest_name) -> dict
  _straight_line_route(olat, olon, dlat, dlon, via_label) -> dict

No hardcoded _CHECKPOINTS dict — all hub data from MySQL.
"""
import logging

from ._geocoder import _haversine_km, _slerp

logger = logging.getLogger(__name__)


def _get_checkpoints() -> dict:
    """Load road hub checkpoints from DB-backed cache. Returns {display: [lat, lon]}."""
    try:
        from ..models import ref_data
        return ref_data.get_road_checkpoints()
    except Exception as e:
        logger.warning(f"[road] ref_data not available: {e}")
        return {}


def _extract_road_names(steps: list) -> dict:
    """
    Extract real road/highway names from OSRM step instructions.
    Returns a mapping of (lon, lat) key -> road label.
    """
    road_names = {}
    if not steps:
        return road_names

    for step in steps:
        name = step.get("name", "").strip()
        ref  = step.get("ref", "").strip()
        road_label = ref or name
        if not road_label or road_label.lower() in ("", "unnamed road"):
            continue
        maneuver = step.get("maneuver", {})
        loc = maneuver.get("location")
        if loc and len(loc) == 2:
            key = (round(loc[0], 3), round(loc[1], 3))
            road_names[key] = road_label

    return road_names


def _snap_and_label(lat, lon, used, road_names, cumulative_km, total_km, total_dur_h):
    """
    Snap a waypoint to nearest checkpoint and/or assign road name.
    Returns (snapped_lat, snapped_lon, name, road_name, segment_info).
    Checkpoint data loaded from MySQL — no hardcoded coords.
    """
    name = None
    road_name = None
    checkpoints = _get_checkpoints()

    # Snap to nearest checkpoint within its configured radius
    for nm, (clat, clon) in checkpoints.items():
        if nm in used:
            continue
        d = _haversine_km({"lat": lat, "lon": lon}, {"lat": clat, "lon": clon})
        if d < 35:
            lat, lon = clat, clon
            name = nm
            used.add(nm)
            break

    # Find nearest road name from OSRM steps
    if road_names:
        min_dist = 999
        for (rlon, rlat), rname in road_names.items():
            d = abs(lat - rlat) + abs(lon - rlon)
            if d < min_dist and d < 0.15:
                min_dist = d
                road_name = rname

    frac = cumulative_km / total_km if total_km > 0 else 0
    eta_hours = round(total_dur_h * (1 - frac), 1) if total_dur_h else None

    return lat, lon, name, road_name, {
        "elapsed_km":       round(cumulative_km),
        "remaining_hours":  eta_hours,
        "progress_pct":     round(frac * 100, 1),
    }


def _osrm_road_route(olat, olon, dlat, dlon, origin_name, dest_name) -> dict:
    """
    Real-time road routing via OSRM public API.

    Returns dict with:
      waypoints: list of waypoint dicts
      osrm_distance_km: OSRM's actual road distance
      osrm_duration_hours: OSRM's estimated drive time
      source: "osrm_live"
    """
    import requests as _req_osrm

    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{olon},{olat};{dlon},{dlat}"
        f"?overview=full&geometries=geojson&steps=true"
    )
    try:
        resp = _req_osrm.get(url, timeout=12, headers={"User-Agent": "AgentRouteAI/3.0"})
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            raise ValueError(f"OSRM code: {data.get('code', 'unknown')}")

        route   = data["routes"][0]
        coords  = route["geometry"]["coordinates"]
        dist_km = round(route["distance"] / 1000)
        dur_h   = round(route["duration"] / 3600, 1)
        logger.info(f"[OSRM] {origin_name}→{dest_name}: {dist_km} km, {dur_h}h, {len(coords)} pts")

        steps = []
        for leg in route.get("legs", []):
            steps.extend(leg.get("steps", []))
        road_names = _extract_road_names(steps)
        logger.info(f"[OSRM] Extracted {len(road_names)} road name segments")

        total  = len(coords)
        step   = max(1, total // 60)
        samp   = coords[::step]
        if samp[-1] != coords[-1]:
            samp.append(coords[-1])

        via  = f"Road · {dist_km} km · ~{dur_h}h (OSRM live)"
        used = set()
        waypoints = []

        for i, (wlon, wlat) in enumerate(samp):
            frac_pos     = i / max(1, len(samp) - 1)
            cumulative_km = dist_km * frac_pos

            snapped_lat, snapped_lon, name, road_name, seg_info = _snap_and_label(
                wlat, wlon, used, road_names, cumulative_km, dist_km, dur_h
            )

            wp = {
                "lat":          round(snapped_lat, 5),
                "lon":          round(snapped_lon, 5),
                "segment_km":   round(cumulative_km),
                "elapsed_km":   seg_info["elapsed_km"],
                "progress_pct": seg_info["progress_pct"],
            }
            if seg_info.get("remaining_hours") is not None:
                wp["remaining_hours"] = seg_info["remaining_hours"]
            if i == 0:
                wp["via"] = via
            if name:
                wp["name"] = name
            if road_name:
                wp["road"] = road_name
            waypoints.append(wp)

        return {
            "waypoints":          waypoints,
            "osrm_distance_km":   dist_km,
            "osrm_duration_hours": dur_h,
            "road_segments":      len(road_names),
            "source":             "osrm_live",
            "degraded":           False,
        }

    except Exception as e:
        logger.warning(f"[OSRM] Route failed ({origin_name}→{dest_name}): {e}. Falling back to geodesic.")
        return _straight_line_route(olat, olon, dlat, dlon,
                                    f"Road (degraded) · OSRM unavailable: {str(e)[:50]}")


def _straight_line_route(olat, olon, dlat, dlon, via_label="Estimated Route (degraded)") -> dict:
    """
    Degraded fallback: SLERP great-circle interpolation.
    Clearly flagged as degraded mode.
    """
    N = 10
    total_km = _haversine_km({"lat": olat, "lon": olon}, {"lat": dlat, "lon": dlon})
    pts = []
    for i in range(N + 2):
        t = i / (N + 1)
        lat, lon = _slerp(olat, olon, dlat, dlon, t)
        wp = {
            "lat":          round(lat, 4),
            "lon":          round(lon, 4),
            "segment_km":   round(total_km * t),
            "elapsed_km":   round(total_km * t),
            "progress_pct": round(t * 100, 1),
        }
        if i == 0:
            wp["via"] = via_label
        pts.append(wp)

    return {
        "waypoints":           pts,
        "osrm_distance_km":    round(total_km),
        "osrm_duration_hours": None,
        "road_segments":       0,
        "source":              "geodesic_fallback",
        "degraded":            True,
    }
