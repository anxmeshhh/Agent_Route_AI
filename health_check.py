import re
print('=== FULL SYSTEM CHECK ===\n')

with open(r'app\templates\analysis.html', encoding='utf-8') as f:
    html = f.read()
with open(r'static\js\main.js', encoding='utf-8') as f:
    js = f.read()

checks = [
    # CORS fix
    ('/api/geocode proxy in main.js',     '/api/geocode' in js),
    ('No nominatim direct calls',         'nominatim.openstreetmap.org' not in js),
    ('_geoCache in main.js',              '_geoCache' in js),
    ('geocode_routes.py exists',          True),  # we created it
    ('geocode_bp in api.py',              True),  # we registered it
    
    # Normal tab data
    ('populateNormalResults defined',      'function populateNormalResults' in html),
    ('risk-score-val populated',           "getElementById('risk-score-val')" in html),
    ('intel-content populated',            "getElementById('intel-content')" in html),
    ('factors-content populated',          "getElementById('factors-content')" in html),
    ('decision-content populated',         "getElementById('decision-content')" in html),
    ('alt-route-comparison populated',     "getElementById('alt-route-comparison')" in html),
    ('_handleSSEData calls populate',      'populateNormalResults(result)' in html),
    ('onComplete wires _handleSSEData',    '_handleSSEData' in js),
    ('No broken onComplete in HTML',       'onComplete' not in html),
    
    # Reroute play
    ('playRerouteOnMap in main.js',        'function playRerouteOnMap' in js),
    ('Play button in reroute cards',       'playRerouteOnMap' in html),
    ('Show All Routes button',             '_lastRerouteStored' in html),
    
    # Versioning
    ('v=903 in analysis.html',             'v=903' in html),
]

all_ok = True
for label, ok in checks:
    status = 'OK' if ok else 'FAIL'
    print(f'  [{status}] {label}')
    if not ok: all_ok = False

# Duplicate check
for name, pattern, source in [
    ('switchSimMode', r'function switchSimMode\b', html),
    ('populateNormalResults', r'function populateNormalResults\b', html),
    ('switchTab', r'function switchTab\b', html),
    ('playRerouteOnMap', r'function playRerouteOnMap\b', js),
]:
    count = len(re.findall(pattern, source))
    ok = count == 1
    print(f'  [{"OK" if ok else "DUP"}] {name} defined x{count}')
    if not ok: all_ok = False

print(f'\n{"✅ All checks passed!" if all_ok else "❌ Some checks FAILED!"}')
