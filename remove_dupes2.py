"""Remove duplicates: genUUID (line 876), fillExample (line 886), THREAT_ICONS (line 1338)."""
path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\analysis.html'
with open(path, encoding='utf-8') as f:
    lines = f.readlines()

# Find exact line ranges to delete (0-indexed)
# We'll find them dynamically
to_delete = []

i = 0
while i < len(lines):
    l = lines[i]
    # 2nd genUUID block (in ticket script) - find and delete lines i to i+4
    if 'function genUUID()' in l and i > 800:
        # Find end of function (next blank line or next function)
        end = i + 1
        while end < len(lines) and '} ' not in lines[end] and lines[end].strip() != '}':
            end += 1
        end += 1  # include the closing }
        print(f"Delete genUUID block: lines {i+1}-{end} (0-indexed {i}-{end-1})")
        to_delete.append((i, end))
        i = end
        continue
    # 2nd fillExample block (in ticket script)
    if 'function fillExample(' in l and i > 800:
        end = i + 1
        while end < len(lines) and '} ' not in lines[end] and lines[end].strip() != '}':
            end += 1
        end += 1
        print(f"Delete fillExample block: lines {i+1}-{end} (0-indexed {i}-{end-1})")
        to_delete.append((i, end))
        i = end
        continue
    # 2nd THREAT_ICONS const (in renderThreatCard area)
    if 'const THREAT_ICONS' in l and i > 1000:
        end = i + 1
        while end < len(lines) and '};' not in lines[end] and '}' not in lines[end]:
            end += 1
        end += 1
        print(f"Delete THREAT_ICONS duplicate: lines {i+1}-{end} (0-indexed {i}-{end-1})")
        to_delete.append((i, end))
        i = end
        continue
    i += 1

# Delete in reverse order to preserve indices
for start, end in sorted(to_delete, reverse=True):
    del lines[start:end]
    print(f"  Deleted lines {start+1}-{end}")

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print(f"\nDone. Total lines: {len(lines)}")
