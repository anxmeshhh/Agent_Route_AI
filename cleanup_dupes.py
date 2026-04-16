"""Clean up analysis.html: remove duplicates and old patch functions."""
path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\analysis.html'
with open(path, encoding='utf-8') as f:
    lines = f.readlines()

original_count = len(lines)

# Ranges to delete (0-indexed), in reverse order so indices don't shift
deletions = []

# 1. Remove old duplicate genUUID + fillExample (lines 716-731, 0-indexed 715-730)
deletions.append((715, 730))

# 2. Remove broken orphan code at lines 1322-1327 (0-indexed 1321-1326)
#    "// ── Update runTicketAnalysis..." + "_origRunTicketAnalysis..." + "}" 
deletions.append((1321, 1326))

# 3. Remove old switchSimPanel (lines 1329-1335, 0-indexed 1328-1334)
# After deletion of 1321-1326, these shift, but we delete in reverse order
deletions.append((1328, 1334))

# 4. Remove old induceThreat function (lines 1348-1373, 0-indexed 1347-1372)
# These reference old 'sim-panels' panel that no longer exists
deletions.append((1347, 1372))

# 5. Remove old getReroutes function (lines 1414-1437, 0-indexed 1413-1436)
# These reference old 'reroute-display' div that no longer exists
deletions.append((1413, 1436))

# Sort in reverse order so we delete from bottom to top
deletions.sort(key=lambda x: x[0], reverse=True)

for start, end in deletions:
    # Safety check
    if end < len(lines):
        print(f"Deleting lines {start+1}-{end+1}: {lines[start].strip()[:60]}...")
        del lines[start:end+1]

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"\nLines: {original_count} -> {len(lines)} (removed {original_count - len(lines)})")
print("Cleanup done.")
