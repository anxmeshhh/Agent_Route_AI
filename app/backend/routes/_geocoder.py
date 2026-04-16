"""
app/routes/_geocoder.py — Geocoding + geospatial primitives

Public API:
  geocode(place)       -> {lat, lon, display} | None
  _haversine_km(p1,p2) -> float
  _slerp(lat1,lon1,lat2,lon2,t) -> (lat, lon)

All coordinate data loaded from MySQL ref_geocoords via ref_data.
No hardcoded KNOWN dict.
"""
import math
import logging

logger = logging.getLogger(__name__)


def _get_geocoords() -> dict:
    """Lazy-load geocoords from DB-backed cache."""
    try:
        from ..models import ref_data
        return ref_data.get_geocoords()
    except Exception as e:
        logger.warning(f"[geocode] ref_data unavailable: {e}")
        return {}


def geocode(place: str):
    """
    Geocode a place name. First checks the DB-backed ref_geocoords cache,
    then falls back to the Nominatim (OpenStreetMap) API.

    Returns: {lat, lon, display} or None
    """
    import requests as _req_r

    pl = place.lower().strip()
    geocoords = _get_geocoords()

    # 1. Exact key match
    if pl in geocoords:
        e = geocoords[pl]
        return {"lat": e["lat"], "lon": e["lon"], "display": e["display"]}

    # 2. Substring match
    for key, e in geocoords.items():
        if key in pl or pl in key:
            return {"lat": e["lat"], "lon": e["lon"], "display": e["display"]}

    # 3. Nominatim fallback — try PLAIN name FIRST (avoids London→London India)
    for q in [place, f"{place}, India"]:
        try:
            r = _req_r.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1},
                headers={"User-Agent": "AgentRouteAI/3.0"},
                timeout=8,
            )
            data = r.json()
            if data:
                return {
                    "lat": float(data[0]["lat"]),
                    "lon": float(data[0]["lon"]),
                    "display": data[0].get("display_name", place),
                }
        except Exception as e:
            logger.warning(f"[geocode] '{q}': {e}")
    return None


# ── Geospatial primitives ─────────────────────────────────────────

def _haversine_km(p1: dict, p2: dict) -> float:
    """Haversine distance in km between two {lat,lon} dicts."""
    R = 6371
    lat1, lon1 = math.radians(p1["lat"]), math.radians(p1["lon"])
    lat2, lon2 = math.radians(p2["lat"]), math.radians(p2["lon"])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _slerp(lat1, lon1, lat2, lon2, t) -> tuple:
    """Spherical linear interpolation (great-circle arc at fraction t)."""
    phi1, lam1 = math.radians(lat1), math.radians(lon1)
    phi2, lam2 = math.radians(lat2), math.radians(lon2)
    dphi, dlam = phi2 - phi1, lam2 - lam1
    a  = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    Om = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0, 1 - a)))
    if Om < 1e-10:
        return lat1, lon1
    A  = math.sin((1-t)*Om) / math.sin(Om)
    B  = math.sin(t*Om)     / math.sin(Om)
    x  = A*math.cos(phi1)*math.cos(lam1) + B*math.cos(phi2)*math.cos(lam2)
    y  = A*math.cos(phi1)*math.sin(lam1) + B*math.cos(phi2)*math.sin(lam2)
    z  = A*math.sin(phi1) + B*math.sin(phi2)
    return math.degrees(math.atan2(z, math.sqrt(x*x + y*y))), math.degrees(math.atan2(y, x))
