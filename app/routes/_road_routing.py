"""
app/routes/_road_routing.py — Production OSRM road routing

All routing is REAL-TIME via OSRM public API:
  - Full road geometry with step-by-step instructions
  - Real road names and highway numbers from OSRM steps
  - Actual distance (km) and duration (hours) from OSRM
  - Named checkpoint snapping for major hubs
  - SLERP geodesic fallback (clearly marked as degraded)

Public API:
  _osrm_road_route(olat, olon, dlat, dlon, origin_name, dest_name) -> dict
  _straight_line_route(olat, olon, dlat, dlon, via_label) -> dict
"""
import logging

from ._geocoder import _haversine_km, _slerp

logger = logging.getLogger(__name__)

# ── Named waypoint checkpoints for snapping (global coverage) ─────
# These are NOT routing data — they are display labels for major
# transport hubs that OSRM geometry passes through.
_CHECKPOINTS = {
    # India
    "Nagpur Junction":     [21.1458, 79.0882],
    "Hyderabad Hub":       [17.3850, 78.4867],
    "Bengaluru Hub":       [12.9716, 77.5946],
    "Coimbatore, NH544":   [11.0168, 76.9558],
    "Kochi Port":          [9.9312,  76.2673],
    "Pune Junction":       [18.5204, 73.8567],
    "Jaipur Hub":          [26.9124, 75.7873],
    "Ahmedabad Hub":       [23.0225, 72.5714],
    "Lucknow Hub":         [26.8467, 80.9462],
    "Surat Hub":           [21.1702, 72.8311],
    "Vadodara Hub":        [22.3072, 73.1812],
    "Bhopal Junction":     [23.2599, 77.4126],
    "Indore Hub":          [22.7196, 75.8577],
    "Visakhapatnam Hub":   [17.6868, 83.2185],
    "Bhubaneswar Hub":     [20.2961, 85.8245],
    "Chennai Junction":    [13.0827, 80.2707],
    "Kolkata Hub":         [22.5726, 88.3639],
    "Patna Hub":           [25.5941, 85.1376],
    "Varanasi Junction":   [25.3176, 82.9739],
    "Agra Hub":            [27.1767, 78.0081],
    "Chandigarh Hub":      [30.7333, 76.7794],
    "Amritsar Hub":        [31.6340, 74.8723],
    "Madurai Hub":         [9.9252,  78.1198],
    "Mangalore Hub":       [12.9141, 74.8560],
    "Mysuru Hub":          [12.2958, 76.6394],
    "Nashik Hub":          [19.9975, 73.7898],
    "Hubli Junction":      [15.3647, 75.1240],
    "Vijayawada Hub":      [16.5062, 80.6480],
    "Guwahati Hub":        [26.1445, 91.7362],
    "Ranchi Hub":          [23.3441, 85.3096],
    "Jodhpur Hub":         [26.2389, 73.0243],
    # South Asia
    "Karachi Hub":         [24.8607, 67.0011],
    "Lahore Hub":          [31.5804, 74.3587],
    "Islamabad Hub":       [33.7294, 73.0931],
    "Colombo Hub":         [6.9271,  79.8612],
    "Dhaka Hub":           [23.8103, 90.4125],
    "Kathmandu Hub":       [27.7172, 85.3240],
    # SE Asia
    "Bangkok Hub":         [13.7563, 100.5018],
    "Kuala Lumpur Hub":    [3.1390,  101.6869],
    "Jakarta Hub":         [-6.2088, 106.8456],
    "Phnom Penh Hub":      [11.5564, 104.9282],
    "Ho Chi Minh Hub":     [10.8231, 106.6297],
    "Hanoi Hub":           [21.0285, 105.8542],
    # East Asia
    "Beijing Hub":         [39.9042, 116.4074],
    "Shanghai Hub":        [31.2304, 121.4737],
    "Guangzhou Hub":       [23.1291, 113.2644],
    "Chengdu Hub":         [30.5728, 104.0668],
    "Wuhan Hub":           [30.5928, 114.3055],
    "Xi'an Hub":           [34.3416, 108.9398],
    "Tokyo Hub":           [35.6762, 139.6503],
    "Osaka Hub":           [34.6937, 135.5023],
    "Seoul Hub":           [37.5665, 126.9780],
    # Europe
    "Paris Hub":           [48.8566, 2.3522],
    "Berlin Hub":          [52.5200, 13.4050],
    "Frankfurt Hub":       [50.1109, 8.6821],
    "Munich Hub":          [48.1351, 11.5820],
    "Hamburg Hub":         [53.5753, 10.0153],
    "London Hub":          [51.5074, -0.1278],
    "Amsterdam Hub":       [52.3676, 4.9041],
    "Brussels Hub":        [50.8503, 4.3517],
    "Milan Hub":           [45.4642, 9.1900],
    "Rome Hub":            [41.9028, 12.4964],
    "Madrid Hub":          [40.4168, -3.7038],
    "Barcelona Hub":       [41.3874, 2.1686],
    "Vienna Hub":          [48.2082, 16.3738],
    "Warsaw Hub":          [52.2297, 21.0122],
    "Prague Hub":          [50.0755, 14.4378],
    "Zurich Hub":          [47.3769, 8.5417],
    "Lyon Hub":            [45.7640, 4.8357],
    "Marseille Hub":       [43.2965, 5.3698],
    "Stockholm Hub":       [59.3293, 18.0686],
    "Copenhagen Hub":      [55.6761, 12.5683],
    "Helsinki Hub":        [60.1699, 24.9384],
    "Oslo Hub":            [59.9139, 10.7522],
    "Athens Hub":          [37.9838, 23.7275],
    "Istanbul Hub":        [41.0082, 28.9784],
    "Bucharest Hub":       [44.4268, 26.1025],
    "Budapest Hub":        [47.4979, 19.0402],
    # Middle East / Africa
    "Dubai Hub":           [25.2048, 55.2708],
    "Riyadh Hub":          [24.7136, 46.6753],
    "Tehran Hub":          [35.6892, 51.3890],
    "Ankara Hub":          [39.9334, 32.8597],
    "Cairo Hub":           [30.0444, 31.2357],
    "Casablanca Hub":      [33.5731, -7.5898],
    "Nairobi Hub":         [-1.2921, 36.8219],
    "Addis Ababa Hub":     [9.0320,  38.7469],
    "Lagos Hub":           [6.5244,  3.3792],
    "Accra Hub":           [5.6037,  -0.1870],
    "Johannesburg Hub":    [-26.2041, 28.0473],
    "Cape Town Hub":       [-33.9249, 18.4241],
    "Dar es Salaam Hub":   [-6.7924, 39.2083],
    # Americas
    "New York Hub":        [40.7128, -74.0060],
    "Los Angeles Hub":     [34.0522, -118.2437],
    "Chicago Hub":         [41.8781, -87.6298],
    "Houston Hub":         [29.7604, -95.3698],
    "Miami Hub":           [25.7617, -80.1918],
    "Atlanta Hub":         [33.7490, -84.3880],
    "Dallas Hub":          [32.7767, -96.7970],
    "Toronto Hub":         [43.6532, -79.3832],
    "Montreal Hub":        [45.5017, -73.5673],
    "Mexico City Hub":     [19.4326, -99.1332],
    "São Paulo Hub":       [-23.5505, -46.6333],
    "Rio de Janeiro Hub":  [-22.9068, -43.1729],
    "Buenos Aires Hub":    [-34.6037, -58.3816],
    "Santiago Hub":        [-33.4489, -70.6693],
    "Bogotá Hub":          [4.7110,  -74.0721],
    "Lima Hub":            [-12.0464, -77.0428],
    # Oceania
    "Sydney Hub":          [-33.8688, 151.2093],
    "Melbourne Hub":       [-37.8136, 144.9631],
    "Brisbane Hub":        [-27.4698, 153.0251],
    "Perth Hub":           [-31.9505, 115.8605],
    "Auckland Hub":        [-36.8485, 174.7633],
}


def _extract_road_names(steps: list) -> dict:
    """
    Extract real road/highway names from OSRM step instructions.
    Returns a mapping of coordinate-index → road name for significant roads.
    """
    road_names = {}
    if not steps:
        return road_names

    for step in steps:
        name = step.get("name", "").strip()
        ref = step.get("ref", "").strip()
        road_label = ref or name
        if not road_label or road_label.lower() in ("", "unnamed road"):
            continue

        # Use the maneuver location as the anchor point
        maneuver = step.get("maneuver", {})
        loc = maneuver.get("location")
        if loc and len(loc) == 2:
            # Store as (lon, lat) → road_label
            key = (round(loc[0], 3), round(loc[1], 3))
            road_names[key] = road_label

    return road_names


def _snap_and_label(lat, lon, used, road_names, cumulative_km, total_km, total_dur_h):
    """
    Snap a waypoint to nearest checkpoint and/or assign road name.
    Returns (snapped_lat, snapped_lon, name, road_name, segment_info).
    """
    name = None
    road_name = None

    # Snap to nearest checkpoint within 35 km
    for nm, (clat, clon) in _CHECKPOINTS.items():
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
            d = abs(lat - rlat) + abs(lon - rlon)  # fast Manhattan approx
            if d < min_dist and d < 0.15:  # ~15km threshold
                min_dist = d
                road_name = rname

    # Compute segment position info
    frac = cumulative_km / total_km if total_km > 0 else 0
    eta_hours = round(total_dur_h * (1 - frac), 1) if total_dur_h else None

    return lat, lon, name, road_name, {"elapsed_km": round(cumulative_km), "remaining_hours": eta_hours, "progress_pct": round(frac * 100, 1)}


def _osrm_road_route(olat, olon, dlat, dlon, origin_name, dest_name) -> dict:
    """
    Real-time road routing via OSRM public API.

    Returns dict with:
      waypoints: list of waypoint dicts
      osrm_distance_km: OSRM's actual road distance (accounts for curves)
      osrm_duration_hours: OSRM's estimated drive time
      source: "osrm_live"
    """
    import requests as _req_osrm

    # OSRM uses lon,lat order (GeoJSON convention)
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

        route    = data["routes"][0]
        coords   = route["geometry"]["coordinates"]   # [[lon, lat], ...]
        dist_km  = round(route["distance"] / 1000)
        dur_h    = round(route["duration"] / 3600, 1)
        logger.info(f"[OSRM] {origin_name}→{dest_name}: {dist_km} km, {dur_h}h, {len(coords)} pts")

        # Extract real road names from OSRM steps
        steps = []
        for leg in route.get("legs", []):
            steps.extend(leg.get("steps", []))
        road_names = _extract_road_names(steps)
        logger.info(f"[OSRM] Extracted {len(road_names)} road name segments")

        # Sample to ~60 points
        total  = len(coords)
        step   = max(1, total // 60)
        samp   = coords[::step]
        if samp[-1] != coords[-1]:
            samp.append(coords[-1])

        via = f"Road · {dist_km} km · ~{dur_h}h (OSRM live)"
        used = set()

        waypoints = []
        for i, (wlon, wlat) in enumerate(samp):
            # Cumulative distance (approximate from sample position)
            frac_pos = i / max(1, len(samp) - 1)
            cumulative_km = dist_km * frac_pos

            snapped_lat, snapped_lon, name, road_name, seg_info = _snap_and_label(
                wlat, wlon, used, road_names, cumulative_km, dist_km, dur_h
            )

            wp = {
                "lat": round(snapped_lat, 5),
                "lon": round(snapped_lon, 5),
                "segment_km": round(cumulative_km),
                "elapsed_km": seg_info["elapsed_km"],
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
            "waypoints": waypoints,
            "osrm_distance_km": dist_km,
            "osrm_duration_hours": dur_h,
            "road_segments": len(road_names),
            "source": "osrm_live",
            "degraded": False,
        }

    except Exception as e:
        logger.warning(f"[OSRM] Route failed ({origin_name}→{dest_name}): {e}. Falling back to geodesic.")
        return _straight_line_route(olat, olon, dlat, dlon,
                                    f"Road (degraded) · OSRM unavailable: {str(e)[:50]}")


def _straight_line_route(olat, olon, dlat, dlon, via_label="Estimated Route (degraded)") -> dict:
    """
    Degraded fallback: SLERP great-circle interpolation (not naive linear).
    Clearly flagged as degraded mode.
    """
    N = 10
    total_km = _haversine_km({"lat": olat, "lon": olon}, {"lat": dlat, "lon": dlon})
    pts = []
    for i in range(N + 2):
        t = i / (N + 1)
        lat, lon = _slerp(olat, olon, dlat, dlon, t)
        wp = {
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "segment_km": round(total_km * t),
            "elapsed_km": round(total_km * t),
            "progress_pct": round(t * 100, 1),
        }
        if i == 0:
            wp["via"] = via_label
        pts.append(wp)

    return {
        "waypoints": pts,
        "osrm_distance_km": round(total_km),
        "osrm_duration_hours": None,
        "road_segments": 0,
        "source": "geodesic_fallback",
        "degraded": True,
    }
