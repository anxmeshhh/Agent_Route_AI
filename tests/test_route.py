import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Simulate what the /api/route endpoint does
# by calling its internal functions directly

# We need the Flask app context for the route module,
# so let's just call the geocoding + waypoint logic by hand

import math

INDIA_CITIES = {
    "delhi":             {"lat": 28.6139, "lon": 77.2090},
    "thiruvananthapuram":{"lat": 8.5241,  "lon": 76.9366},
    "mumbai":            {"lat": 19.0760, "lon": 72.8777},
    "bangalore":         {"lat": 12.9716, "lon": 77.5946},
    "kolkata":           {"lat": 22.5726, "lon": 88.3639},
    "shanghai":          {"lat": 31.2304, "lon": 121.4737},
    "rotterdam":         {"lat": 51.9225, "lon": 4.4792},
}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    d = lambda a: math.radians(a)
    dLat = d(lat2 - lat1); dLon = d(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(d(lat1)) * math.cos(d(lat2)) * math.sin(dLon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

routes = [
    ("Delhi", "Thiruvananthapuram"),
    ("Mumbai", "Bangalore"),
    ("Delhi", "Kolkata"),
    ("Shanghai", "Rotterdam"),
]

print("=" * 70)
print("ROUTE API SANITY CHECK")
print("=" * 70)

for orig, dest in routes:
    og = INDIA_CITIES.get(orig.lower())
    dg = INDIA_CITIES.get(dest.lower())
    if og and dg:
        km = haversine(og["lat"], og["lon"], dg["lat"], dg["lon"])
        same = (og["lat"] == dg["lat"] and og["lon"] == dg["lon"])
        status = "FAIL-SAME-COORDS" if same else "OK"
        print(f"[{status}] {orig} -> {dest}: straight-line ~{km:.0f} km")
        if same:
            print("      *** ORIGIN == DEST COORDS — animation would break! ***")
    else:
        print(f"[SKIP] {orig} -> {dest}: not in local dict")

print()
print("Now testing actual Flask route endpoint...")
print("Starting Flask app in test mode...")

# Start the actual app and test the endpoint
import subprocess, time
result = subprocess.run(
    ["python", "-c",
     "import requests; r = requests.get('http://127.0.0.1:5000/api/route?origin=Delhi&dest=Thiruvananthapuram'); print(r.status_code); d = r.json(); print('waypoints:', len(d.get('waypoints', []))); print('total_km:', d.get('total_km')); print('is_land:', d.get('is_land_route')); [print(' WP:', w.get('name', '-'), w['lat'][:6] if isinstance(w['lat'], str) else round(w['lat'],2), w['lon'][:6] if isinstance(w['lon'], str) else round(w['lon'],2)) for w in d.get('waypoints',[])]"],
    cwd=os.path.dirname(os.path.abspath(__file__)),
    capture_output=True, text=True, timeout=15
)
print(result.stdout)
if result.stderr:
    print("ERR:", result.stderr[:300])
