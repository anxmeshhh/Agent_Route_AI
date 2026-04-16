"""Fix _threatTicketId in renderThreatCard and also remove the orphaned getReroutes comment stub."""
path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\analysis.html'
with open(path, encoding='utf-8') as f:
    content = f.read()

# Fix 1: Replace _threatTicketId reference in reroute button
old = "onclick=\"getReroutes('${_threatTicketId}',event)\">🔀 Generate Reroutes & Suggestions"
new = "onclick=\"switchSimMode('suggest',document.getElementById('simtab-suggest'));genReroutesFromPanel();\">🔀 Go to Suggestions & Reroutes"
if old in content:
    content = content.replace(old, new)
    print("Fixed: _threatTicketId -> _activeTicket reroute button")
else:
    print("WARNING: Target string not found, trying partial match...")
    # Find the line with _threatTicketId and show context
    for i, line in enumerate(content.splitlines(), 1):
        if '_threatTicketId' in line:
            print(f"  Line {i}: {line.strip()}")

# Fix 2: Remove orphaned comment "// ── GET REROUTES ──" stub
old2 = "\n// ── GET REROUTES ──────────────────────────────────────\n\nfunction renderReroutes"
new2 = "\nfunction renderReroutes"
if old2 in content:
    content = content.replace(old2, new2)
    print("Removed orphaned GET REROUTES comment stub")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done.")
