"""
app/routes/_detect_mode.py — Auto-detect transport mode from geography

Public API:
  _detect_transport_mode(olat, olon, dlat, dlon, origin_name, dest_name) -> str
"""
from ._geocoder import _haversine_km


def _detect_transport_mode(olat, olon, dlat, dlon, origin_name, dest_name) -> str:
    """
    Auto-detect transport mode.
    Priority: explicit air keywords → India road → same-continent road → maritime.
    """
    on, dn = origin_name.lower(), dest_name.lower()
    air_kw = ["airport", "air", "fly", "flight", "airways", "airline"]
    if any(k in on or k in dn for k in air_kw):
        return "air"

    INDIA = {"lat_min": 6.5, "lat_max": 37.5, "lon_min": 68.0, "lon_max": 97.5}
    def in_india(lat, lon):
        return INDIA["lat_min"] <= lat <= INDIA["lat_max"] and INDIA["lon_min"] <= lon <= INDIA["lon_max"]
    if in_india(olat, olon) and in_india(dlat, dlon):
        return "road"

    dist = _haversine_km({"lat": olat, "lon": olon}, {"lat": dlat, "lon": dlon})

    def region(lat, lon):
        # Europe (includes UK, Portugal, Scandinavia)
        if 34 <= lat <= 72 and -15 <= lon <= 45:   return "europe"
        # North America
        if 15 <= lat <= 75 and -170 <= lon <= -50: return "north_america"
        # South America
        if -60 <= lat <= 15 and -85 <= lon <= -30: return "south_america"
        # Asia (Far East + SE Asia)
        if 5  <= lat <= 60 and 55 <= lon <= 150:   return "asia"
        # Africa / Middle East (mostly maritime for long haul)
        if -40 <= lat <= 40 and -20 <= lon <= 55:  return "africa_me"
        return "ocean"

    rO, rD = region(olat, olon), region(dlat, dlon)
    if rO == rD and rO not in ("ocean",) and dist < 6000:
        return "road"
    return "sea"
