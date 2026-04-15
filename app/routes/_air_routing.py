"""
app/routes/_air_routing.py — Great-circle air routing with airport snapping

Public API:
  _air_route_waypoints(olat, olon, dlat, dlon, origin_name, dest_name) -> list
"""
from ._geocoder import _haversine_km, _slerp

# ── International airports database ──────────────────────────────
AIRPORTS = {
    "DEL — Indira Gandhi Intl":      [28.5562, 77.1000],
    "BOM — Chhatrapati Shivaji Intl":[19.0896, 72.8656],
    "BLR — Kempegowda Intl":         [13.1986, 77.7066],
    "MAA — Chennai Intl":            [12.9941, 80.1709],
    "CCU — Netaji Subhas Intl":      [22.6547, 88.4467],
    "HYD — Rajiv Gandhi Intl":       [17.2403, 78.4294],
    "COK — Cochin Intl":             [10.1520, 76.4019],
    "AMD — Sardar Vallabhbhai Intl": [23.0770, 72.6347],
    "LHR — Heathrow":                [51.4775, -0.4614],
    "CDG — Charles de Gaulle":       [49.0097, 2.5478],
    "FRA — Frankfurt":               [50.0379, 8.5622],
    "AMS — Schiphol":                [52.3086, 4.7639],
    "DXB — Dubai Intl":              [25.2532, 55.3657],
    "SIN — Changi":                  [1.3644,  103.9915],
    "HKG — Hong Kong Intl":          [22.3080, 113.9185],
    "NRT — Tokyo Narita":            [35.7720, 140.3929],
    "JFK — John F Kennedy":          [40.6413, -73.7781],
    "ORD — O'Hare":                  [41.9742, -87.9073],
    "LAX — Los Angeles Intl":        [33.9425, -118.4081],
    "SYD — Kingsford Smith":         [-33.9399, 151.1753],
    "DOH — Doha Hamad Intl":         [25.2731, 51.6080],
    "IST — Istanbul Intl":           [41.2753, 28.7519],
    "ICN — Incheon":                 [37.4602, 126.4407],
    "PEK — Beijing Capital":         [40.0799, 116.6031],
    "PVG — Shanghai Pudong":         [31.1443, 121.8083],
    "KUL — KLIA":                    [2.7456,  101.7100],
    "GRU — São Paulo Guarulhos":     [-23.4356, -46.4731],
    "JNB — OR Tambo":                [-26.1367, 28.2411],
    "NBO — Nairobi Jomo Kenyatta":   [-1.3192, 36.9275],
}


def _air_route_waypoints(olat, olon, dlat, dlon, origin_name, dest_name) -> list:
    """
    Great-circle geodesic arc for air routes.
    Uses SLERP (spherical linear interpolation) for accurate arc geometry.
    Snaps to known international airports within 80 km.
    """
    N   = 60  # number of arc segments
    via = "Air Route · Great-Circle Arc"
    used_airports = set()
    waypoints = []

    for i in range(N + 1):
        t             = i / N
        lat, lon      = _slerp(olat, olon, dlat, dlon, t)
        wp            = {"lat": round(lat, 4), "lon": round(lon, 4)}
        if i == 0:
            wp["via"] = via
        # Snap to airport
        for aname, (alat, alon) in AIRPORTS.items():
            if aname not in used_airports:
                d = _haversine_km({"lat": lat, "lon": lon}, {"lat": alat, "lon": alon})
                if d < 80:
                    wp.update({"lat": round(alat, 4), "lon": round(alon, 4), "name": aname})
                    used_airports.add(aname)
                    break
        waypoints.append(wp)

    return waypoints
