"""Test ALL transport modes — Road (OSRM), Maritime (geography), Air (SLERP) — globally."""
import urllib.request, urllib.parse, json, time
time.sleep(3)  # wait for Flask reload

tests = [
    # Indian road routes (auto-detected as 'road')
    ("Nagpur",      "Bangalore",       "road"),
    ("Delhi",       "Thiruvananthapuram","road"),
    ("Mumbai",      "Kolkata",          "road"),
    ("Chennai",     "Kochi",            "road"),
    # European road routes
    ("London",      "Paris",            "road"),
    ("Hamburg",      "Berlin",           "road"),
    ("Madrid",       "Barcelona",        "road"),
    # US road routes  
    ("Los Angeles",  "New York",         "road"),
    ("Chicago",      "Miami",            "road"),
    # Maritime routes (auto-detected as 'sea')
    ("Shanghai",     "Rotterdam",        "sea"),
    ("Dubai",        "Singapore",        "sea"),
    ("Mumbai",       "Hamburg",          "sea"),  
    ("Tokyo",        "Los Angeles",      "sea"),
    # Air routes (explicit mode=air)
    ("Delhi",        "London",           "air"),
    ("New York",     "Tokyo",            "air"),
]

print("=" * 90)
print("{:<16} {:<20} {:<6} {:<8} {:<8} {}".format(
    "ORIGIN", "DEST", "MODE", "KM", "PTS", "CHECKPOINTS"))
print("=" * 90)

for origin, dest, expected in tests:
    # Use mode=auto for road/sea, mode=air for explicit air
    mode = "air" if expected == "air" else "auto"
    url = "http://127.0.0.1:5000/api/route?origin={}&dest={}&mode={}".format(
        urllib.parse.quote(origin), urllib.parse.quote(dest), mode
    )
    try:
        r = urllib.request.urlopen(url, timeout=25)
        d = json.loads(r.read())
        wps   = d.get("waypoints", [])
        named = [w["name"] for w in wps if "name" in w]
        actual_mode = d.get("transport_mode", "?")
        km    = d.get("total_km", "?")
        ok    = "OK" if actual_mode == expected else "MISMATCH"
        mark  = "  " if ok == "OK" else "!!"
        print("{}{:<16} {:<20} {:<6} {:>7} {:>4}pts  {}".format(
            mark, origin, dest, actual_mode, km, len(wps), named[:4]))
        if ok != "OK":
            print("   ^^^ EXPECTED {} but got {}".format(expected, actual_mode))
    except Exception as e:
        print("!! {:<16} {:<20} ERROR: {}".format(origin, dest, str(e)[:60]))

print("=" * 90)
print("DONE")
