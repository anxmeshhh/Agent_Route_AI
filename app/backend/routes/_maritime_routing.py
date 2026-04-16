"""
app/routes/_maritime_routing.py — Chokepoint-based maritime routing

Public API:
  _maritime_waypoints(olat, olon, dlat, dlon, origin_name, dest_name) -> list

All chokepoint coordinates and route tables are loaded from MySQL
ref_geocoords + ref_maritime_routes via ref_data.
No hardcoded ROUTE_TABLE or inline chokepoint coordinate dicts.
"""
import logging

from ._geocoder import _slerp

logger = logging.getLogger(__name__)


def _get_maritime_routes() -> dict:
    """Load maritime route table from DB cache."""
    try:
        from ..models import ref_data
        return ref_data.get_maritime_routes()
    except Exception as e:
        logger.warning(f"[maritime] ref_data unavailable: {e}")
        return {}


def _maritime_waypoints(olat, olon, dlat, dlon, origin_name, dest_name):
    """
    GEOGRAPHY-BASED maritime routing — uses lat/lon bounding regions
    (not port-name matching) so ANY origin→dest pair gets proper
    chokepoint routing.

    Route table and chokepoint coordinates loaded from MySQL ref_maritime_routes
    + ref_geocoords. Zero hardcoded dicts.
    """

    # Geographic region classifier — pure math, no hardcoded port names
    def _sea_region(lat, lon):
        if -10 <= lat <= 55 and 100 <= lon <= 150: return "east_asia"
        if -10 <= lat <= 30 and 60 <= lon < 100:   return "indian_ocean"
        if 15 <= lat <= 35 and 40 <= lon < 60:     return "middle_east"
        if 34 <= lat <= 72 and -15 <= lon <= 45:   return "europe"
        if 15 <= lat <= 75 and -170 <= lon <= -50: return "us_east" if lon > -100 else "us_west"
        if -60 <= lat <= 15 and -85 <= lon <= -30: return "south_america"
        if -40 <= lat <= 35 and -20 <= lon <= 55:  return "africa"
        if -50 <= lat <= 0 and 100 <= lon <= 180:  return "oceania"
        return "ocean"

    rO = _sea_region(olat, olon)
    rD = _sea_region(dlat, dlon)
    logger.info(f"[maritime] {origin_name} ({rO}) → {dest_name} ({rD})")

    route_table = _get_maritime_routes()
    route_key   = (rO, rD)
    reverse_key = (rD, rO)

    # Resolve chokepoints from DB
    chokepoints = []
    if route_key in route_table:
        chokepoints = route_table[route_key]
    elif reverse_key in route_table:
        chokepoints = list(reversed(route_table[reverse_key]))
    else:
        # Fallback: great-circle with 5 intermediate ocean points
        logger.info(f"[maritime] No route table entry for {rO}→{rD}, using great-circle")
        N = 5
        for i in range(1, N + 1):
            t = i / (N + 1)
            lat, lon = _slerp(olat, olon, dlat, dlon, t)
            chokepoints.append({
                "lat": round(lat, 2), "lon": round(lon, 2),
                "name": f"Waypoint {i}",
            })

    # Build via label from chokepoint names
    names = [cp["name"] for cp in chokepoints if cp.get("name")]
    via   = " → ".join(names[:4]) if names else "Direct Maritime"

    # Assemble full waypoint list
    result = [{"lat": olat, "lon": olon, "via": f"Maritime · {via}"}]
    for cp in chokepoints:
        result.append({"lat": cp["lat"], "lon": cp["lon"], "name": cp.get("name", "")})
    result.append({"lat": dlat, "lon": dlon})

    return result
