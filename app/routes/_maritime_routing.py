"""
app/routes/_maritime_routing.py — Chokepoint-based maritime routing

Public API:
  _maritime_waypoints(olat, olon, dlat, dlon, origin_name, dest_name) -> list
"""
import logging

from ._geocoder import _slerp

logger = logging.getLogger(__name__)


def _maritime_waypoints(olat, olon, dlat, dlon, origin_name, dest_name):
    """
    GEOGRAPHY-BASED maritime routing — uses lat/lon bounding regions
    (not port-name matching) so ANY origin→dest pair gets proper
    chokepoint routing. Works for cities, ports, or any geocoded point.
    """
    # Chokepoint coordinates
    SUEZ        = {"lat": 30.0,  "lon": 32.55,  "name": "Suez Canal"}
    BAB_MANDEB  = {"lat": 12.65, "lon": 43.30,  "name": "Bab el-Mandeb"}
    GIBRALTAR   = {"lat": 35.95, "lon": -5.45,  "name": "Strait of Gibraltar"}
    MALACCA     = {"lat": 1.25,  "lon": 103.65, "name": "Malacca Strait"}
    HORMUZ      = {"lat": 26.56, "lon": 56.25,  "name": "Strait of Hormuz"}
    PANAMA      = {"lat": 8.99,  "lon": -79.57, "name": "Panama Canal"}
    CAPE_HOPE   = {"lat": -34.36,"lon": 18.47,  "name": "Cape of Good Hope"}
    DOVER       = {"lat": 51.11, "lon": 1.35,   "name": "Dover Strait"}
    S_CHINA_SEA = {"lat": 12.0,  "lon": 114.0,  "name": "South China Sea"}
    ARABIAN_SEA = {"lat": 15.0,  "lon": 65.0,   "name": "Arabian Sea"}
    MED_EAST    = {"lat": 34.0,  "lon": 25.0,   "name": "Eastern Mediterranean"}
    N_PACIFIC_E = {"lat": 35.0,  "lon": 150.0,  "name": "North Pacific (E)"}
    N_PACIFIC_W = {"lat": 35.0,  "lon": -145.0, "name": "North Pacific (W)"}
    N_ATLANTIC  = {"lat": 45.0,  "lon": -30.0,  "name": "North Atlantic"}
    S_ATLANTIC  = {"lat": -15.0, "lon": -25.0,  "name": "South Atlantic"}

    # Classify origin/dest into maritime regions by geography
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

    # Build ordered chokepoint list based on origin→dest regions
    route_key = (rO, rD)
    reverse_key = (rD, rO)

    ROUTE_TABLE = {
        ("east_asia", "europe"):       [S_CHINA_SEA, MALACCA, ARABIAN_SEA, BAB_MANDEB, SUEZ, MED_EAST, GIBRALTAR],
        ("east_asia", "middle_east"):  [S_CHINA_SEA, MALACCA, ARABIAN_SEA, HORMUZ],
        ("east_asia", "indian_ocean"): [S_CHINA_SEA, MALACCA],
        ("east_asia", "us_west"):      [N_PACIFIC_E, N_PACIFIC_W],
        ("east_asia", "us_east"):      [S_CHINA_SEA, MALACCA, ARABIAN_SEA, BAB_MANDEB, SUEZ, MED_EAST, GIBRALTAR, N_ATLANTIC],
        ("east_asia", "africa"):       [S_CHINA_SEA, MALACCA, ARABIAN_SEA, BAB_MANDEB],
        ("east_asia", "south_america"): [N_PACIFIC_E, N_PACIFIC_W, PANAMA],
        ("east_asia", "oceania"):      [S_CHINA_SEA],
        ("indian_ocean", "europe"):    [ARABIAN_SEA, BAB_MANDEB, SUEZ, MED_EAST, GIBRALTAR],
        ("indian_ocean", "middle_east"): [ARABIAN_SEA, HORMUZ],
        ("indian_ocean", "us_east"):   [ARABIAN_SEA, BAB_MANDEB, SUEZ, GIBRALTAR, N_ATLANTIC],
        ("indian_ocean", "africa"):    [ARABIAN_SEA, BAB_MANDEB],
        ("indian_ocean", "east_asia"): [MALACCA, S_CHINA_SEA],
        ("europe", "us_east"):         [DOVER, N_ATLANTIC],
        ("europe", "us_west"):         [GIBRALTAR, PANAMA],
        ("europe", "south_america"):   [GIBRALTAR, S_ATLANTIC],
        ("europe", "middle_east"):     [GIBRALTAR, MED_EAST, SUEZ, BAB_MANDEB, HORMUZ],
        ("europe", "africa"):          [GIBRALTAR],
        ("europe", "indian_ocean"):    [GIBRALTAR, MED_EAST, SUEZ, BAB_MANDEB, ARABIAN_SEA],
        ("europe", "oceania"):         [GIBRALTAR, MED_EAST, SUEZ, BAB_MANDEB, ARABIAN_SEA, MALACCA, S_CHINA_SEA],
        ("middle_east", "europe"):     [HORMUZ, BAB_MANDEB, SUEZ, MED_EAST, GIBRALTAR],
        ("middle_east", "us_east"):    [HORMUZ, BAB_MANDEB, SUEZ, GIBRALTAR, N_ATLANTIC],
        ("middle_east", "africa"):     [HORMUZ, BAB_MANDEB],
        ("middle_east", "east_asia"):  [HORMUZ, ARABIAN_SEA, MALACCA, S_CHINA_SEA],
        ("middle_east", "indian_ocean"): [HORMUZ, ARABIAN_SEA],
        ("us_east", "south_america"):  [S_ATLANTIC],
        ("us_west", "south_america"):  [PANAMA],
        ("us_west", "east_asia"):      [N_PACIFIC_W, N_PACIFIC_E],
        ("us_east", "europe"):         [N_ATLANTIC, DOVER],
        ("africa", "south_america"):   [CAPE_HOPE, S_ATLANTIC],
        ("africa", "europe"):          [GIBRALTAR],
        ("africa", "east_asia"):       [BAB_MANDEB, ARABIAN_SEA, MALACCA, S_CHINA_SEA],
        ("africa", "indian_ocean"):    [BAB_MANDEB, ARABIAN_SEA],
    }

    # Look up route or reversed route
    chokepoints = []
    if route_key in ROUTE_TABLE:
        chokepoints = ROUTE_TABLE[route_key]
    elif reverse_key in ROUTE_TABLE:
        chokepoints = list(reversed(ROUTE_TABLE[reverse_key]))
    else:
        # Fallback: great-circle with 5 intermediate ocean points
        logger.info(f"[maritime] No chokepoint table for {rO}→{rD}, using great-circle")
        N = 5
        for i in range(1, N + 1):
            t = i / (N + 1)
            lat, lon = _slerp(olat, olon, dlat, dlon, t)
            chokepoints.append({"lat": round(lat, 2), "lon": round(lon, 2), "name": f"Waypoint {i}"})

    # Build via label from chokepoint names
    names = [cp["name"] for cp in chokepoints if "name" in cp]
    via = " → ".join(names[:4]) if names else "Direct Maritime"

    # Assemble full waypoint list
    result = [{"lat": olat, "lon": olon, "via": f"Maritime · {via}"}]
    for cp in chokepoints:
        result.append({"lat": cp["lat"], "lon": cp["lon"], "name": cp.get("name", "")})
    result.append({"lat": dlat, "lon": dlon})

    return result
