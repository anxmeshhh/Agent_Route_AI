"""
app/routes/_geocoder.py — Geocoding + geospatial primitives

Public API:
  KNOWN               — dict of ~150 city/port → [lat, lon]
  geocode(place)       → {lat, lon, display} | None
  _haversine_km(p1,p2) → float
  _slerp(lat1,lon1,lat2,lon2,t) → (lat, lon)
"""
import math
import logging

logger = logging.getLogger(__name__)

# ── Known city/port coordinates ───────────────────────────────────
KNOWN = {
    # India
    "delhi": [28.6139, 77.2090], "new delhi": [28.6139, 77.2090],
    "mumbai": [19.0760, 72.8777], "bombay": [19.0760, 72.8777],
    "bangalore": [12.9716, 77.5946], "bengaluru": [12.9716, 77.5946],
    "chennai": [13.0827, 80.2707], "madras": [13.0827, 80.2707],
    "kolkata": [22.5726, 88.3639], "calcutta": [22.5726, 88.3639],
    "hyderabad": [17.3850, 78.4867], "secunderabad": [17.4399, 78.4983],
    "pune": [18.5204, 73.8567],
    "ahmedabad": [23.0225, 72.5714],
    "jaipur": [26.9124, 75.7873],
    "lucknow": [26.8467, 80.9462],
    "nagpur": [21.1458, 79.0882],
    "coimbatore": [11.0168, 76.9558],
    "kochi": [9.9312, 76.2673], "cochin": [9.9312, 76.2673],
    "trivandrum": [8.5241, 76.9366], "thiruvananthapuram": [8.5241, 76.9366],
    "kerala": [10.8505, 76.2711],
    "indore": [22.7196, 75.8577],
    "bhopal": [23.2599, 77.4126],
    "surat": [21.1702, 72.8311],
    "vadodara": [22.3072, 73.1812], "baroda": [22.3072, 73.1812],
    "patna": [25.5941, 85.1376],
    "bhubaneswar": [20.2961, 85.8245],
    "visakhapatnam": [17.6868, 83.2185], "vizag": [17.6868, 83.2185],
    "madurai": [9.9252, 78.1198],
    "amritsar": [31.6340, 74.8723],
    "chandigarh": [30.7333, 76.7794],
    "jodhpur": [26.2389, 73.0243],
    "agra": [27.1767, 78.0081],
    "varanasi": [25.3176, 82.9739],
    "guwahati": [26.1445, 91.7362],
    "raipur": [21.2514, 81.6296],
    "ranchi": [23.3441, 85.3096],
    "dehradun": [30.3165, 78.0322],
    "vijayawada": [16.5062, 80.6480],
    "mangalore": [12.9141, 74.8560],
    "mysore": [12.2958, 76.6394], "mysuru": [12.2958, 76.6394],
    "tiruchirappalli": [10.7905, 78.7047], "trichy": [10.7905, 78.7047],
    "nashik": [19.9975, 73.7898],
    "aurangabad": [19.8762, 75.3433],
    "ludhiana": [30.9010, 75.8573],
    "thirupur": [11.1085, 77.3411],
    "hubli": [15.3647, 75.1240],
    "belgaum": [15.8497, 74.4977], "belagavi": [15.8497, 74.4977],
    "nhava sheva": [18.9500, 72.9500],
    "mundra": [22.8393, 69.7212],
    # Global cities & ports (comprehensive)
    "shanghai": [31.2304, 121.4737],
    "ningbo": [29.8683, 121.5440],
    "shenzhen": [22.5431, 114.0579],
    "tianjin": [39.3434, 117.3616],
    "qingdao": [36.0671, 120.3826],
    "guangzhou": [23.1291, 113.2644],
    "hong kong": [22.3193, 114.1694],
    "busan": [35.1796, 129.0756],
    "tokyo": [35.6762, 139.6503],
    "osaka": [34.6937, 135.5023],
    "rotterdam": [51.9225, 4.4792],
    "hamburg": [53.5753, 10.0153],
    "antwerp": [51.2608, 4.3946],
    "felixstowe": [51.9554, 1.3519],
    "barcelona": [41.3874, 2.1686],
    "genoa": [44.4056, 8.9463],
    "marseille": [43.2965, 5.3698],
    "piraeus": [37.9475, 23.6452],
    "le havre": [49.4944, 0.1079],
    "singapore": [1.3521, 103.8198],
    "jebel ali": [24.9857, 55.0919],
    "dubai": [25.2048, 55.2708],
    "abu dhabi": [24.4539, 54.3773],
    "salalah": [17.0239, 54.0924],
    "colombo": [6.9271, 79.8612],
    "los angeles": [33.7701, -118.1937],
    "long beach": [33.7701, -118.1937],
    "new york": [40.6643, -74.0000],
    "seattle": [47.6062, -122.3321],
    "houston": [29.7604, -95.3698],
    "savannah": [32.0835, -81.0998],
    "santos": [-23.9618, -46.3322],
    "callao": [-12.0553, -77.1184],
    "durban": [-29.8587, 31.0218],
    "mombasa": [-4.0435, 39.6682],
    "lagos": [6.5244, 3.3792],
    "dar es salaam": [-6.7924, 39.2083],
    "sydney": [-33.8688, 151.2093],
    "melbourne": [-37.8136, 144.9631],
    # Europe — major cities (NOT ports only)
    "london": [51.5074, -0.1278],
    "paris": [48.8566, 2.3522],
    "berlin": [52.5200, 13.4050],
    "madrid": [40.4168, -3.7038],
    "rome": [41.9028, 12.4964],
    "milan": [45.4642, 9.1900],
    "amsterdam": [52.3676, 4.9041],
    "brussels": [50.8503, 4.3517],
    "vienna": [48.2082, 16.3738],
    "zurich": [47.3769, 8.5417],
    "munich": [48.1351, 11.5820],
    "frankfurt": [50.1109, 8.6821],
    "warsaw": [52.2297, 21.0122],
    "prague": [50.0755, 14.4378],
    "lisbon": [38.7223, -9.1393],
    "athens": [37.9838, 23.7275],
    "istanbul": [41.0082, 28.9784],
    "copenhagen": [55.6761, 12.5683],
    "stockholm": [59.3293, 18.0686],
    "oslo": [59.9139, 10.7522],
    "helsinki": [60.1699, 24.9384],
    "budapest": [47.4979, 19.0402],
    "bucharest": [44.4268, 26.1025],
    "lyon": [45.7640, 4.8357],
    # Americas — major cities
    "chicago": [41.8781, -87.6298],
    "san francisco": [37.7749, -122.4194],
    "miami": [25.7617, -80.1918],
    "atlanta": [33.7490, -84.3880],
    "dallas": [32.7767, -96.7970],
    "denver": [39.7392, -104.9903],
    "toronto": [43.6532, -79.3832],
    "vancouver": [49.2827, -123.1207],
    "montreal": [45.5017, -73.5673],
    "mexico city": [19.4326, -99.1332],
    "bogota": [4.7110, -74.0721],
    "lima": [-12.0464, -77.0428],
    "santiago": [-33.4489, -70.6693],
    "buenos aires": [-34.6037, -58.3816],
    "rio de janeiro": [-22.9068, -43.1729],
    "sao paulo": [-23.5505, -46.6333],
    # Africa / Middle East — major cities
    "cairo": [30.0444, 31.2357],
    "nairobi": [-1.2921, 36.8219],
    "johannesburg": [-26.2041, 28.0473],
    "cape town": [-33.9249, 18.4241],
    "casablanca": [33.5731, -7.5898],
    "riyadh": [24.7136, 46.6753],
    "doha": [25.2854, 51.5310],
    "tehran": [35.6892, 51.3890],
    "ankara": [39.9334, 32.8597],
    "addis ababa": [9.0320, 38.7469],
    "accra": [5.6037, -0.1870],
    # Asia — other major cities
    "bangkok": [13.7563, 100.5018],
    "kuala lumpur": [3.1390, 101.6869],
    "jakarta": [-6.2088, 106.8456],
    "manila": [14.5995, 120.9842],
    "ho chi minh": [10.8231, 106.6297],
    "hanoi": [21.0285, 105.8542],
    "seoul": [37.5665, 126.9780],
    "beijing": [39.9042, 116.4074],
    "taipei": [25.0330, 121.5654],
    # Oceania
    "brisbane": [-27.4698, 153.0251],
    "perth": [-31.9505, 115.8605],
    "auckland": [-36.8485, 174.7633],
}


def geocode(place: str):
    """
    Geocode a place name. First checks the KNOWN table, then falls back to
    the Nominatim (OpenStreetMap) API.

    Returns: {lat, lon, display} or None
    """
    import requests as _req_r

    pl = place.lower().strip()
    for key, coords in KNOWN.items():
        if key in pl or pl in key:
            return {"lat": coords[0], "lon": coords[1], "display": place}
    # Nominatim fallback — try PLAIN name FIRST (avoids London→London India)
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
