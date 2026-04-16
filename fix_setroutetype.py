"""Fix the infinite recursion in setRouteType inside analysis.html."""
path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\analysis.html'
with open(path, encoding='utf-8') as f:
    html = f.read()

# Remove the bad recursive block (4 lines)
bad = """let _currentRouteType = 'road';
const _origSetRouteType = typeof setRouteType === 'function' ? setRouteType : null;
function setRouteType(t) {
    _currentRouteType = t;
    if (_origSetRouteType) _origSetRouteType(t);
    document.querySelectorAll('.route-type-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-'+t)?.classList.add('active');
}"""

good = """let _currentRouteType = 'road';
function setRouteType(t) {
    _currentRouteType = t;
    document.querySelectorAll('.route-type-btn').forEach(b => b.classList.remove('active'));
    const map = {road:'btn-land', sea:'btn-sea', air:'btn-air'};
    document.getElementById(map[t] || 'btn-land')?.classList.add('active');
}"""

if bad in html:
    html = html.replace(bad, good, 1)
    print("Fixed recursive setRouteType")
else:
    # line-by-line fallback
    found = False
    lines = html.split('\n')
    out = []
    skip_next = False
    for i, line in enumerate(lines):
        if '_origSetRouteType' in line:
            print(f"Removing line {i+1}: {line.rstrip()}")
            continue
        out.append(line)
    html = '\n'.join(out)
    print("Removed _origSetRouteType lines via fallback")

with open(path, 'w', encoding='utf-8') as f:
    f.write(html)
print("Done.")
