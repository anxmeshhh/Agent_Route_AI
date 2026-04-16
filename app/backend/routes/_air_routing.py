"""
app/routes/_air_routing.py — Great-circle air routing with airport snapping

Public API:
  _air_route_waypoints(olat, olon, dlat, dlon, origin_name, dest_name) -> list

Airport coordinates loaded from MySQL ref_geocoords via ref_data.
No hardcoded AIRPORTS dict.
"""
from ._geocoder import _haversine_km, _slerp


def _get_airports() -> dict:
    """Load airports from DB-backed cache. Returns {name_key: entry_dict}."""
    try:
        from ..models import ref_data
        return ref_data.get_airports()
    except Exception:
        return {}


def _air_route_waypoints(olat, olon, dlat, dlon, origin_name, dest_name) -> list:
    """
    Great-circle geodesic arc for air routes.
    Uses SLERP (spherical linear interpolation) for accurate arc geometry.
    Snaps to known international airports within their configured snap_radius_km.
    Airport data loaded from MySQL ref_geocoords — no hardcoded AIRPORTS dict.
    """
    N   = 60  # number of arc segments
    via = "Air Route · Great-Circle Arc"
    used_airports = set()
    waypoints = []

    airports = _get_airports()

    for i in range(N + 1):
        t        = i / N
        lat, lon = _slerp(olat, olon, dlat, dlon, t)
        wp       = {"lat": round(lat, 4), "lon": round(lon, 4)}
        if i == 0:
            wp["via"] = via

        # Snap to nearest airport within its configured radius
        for akey, entry in airports.items():
            if akey in used_airports:
                continue
            alat = entry["lat"]
            alon = entry["lon"]
            snap_km = entry.get("snap_radius_km", 80)
            d = _haversine_km({"lat": lat, "lon": lon}, {"lat": alat, "lon": alon})
            if d < snap_km:
                # Use iata_code + display for the name label
                label = entry.get("display") or akey.upper()
                wp.update({"lat": round(alat, 4), "lon": round(alon, 4), "name": label})
                used_airports.add(akey)
                break

        waypoints.append(wp)

    return waypoints
