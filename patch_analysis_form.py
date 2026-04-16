"""One-shot script to patch analysis.html with the structured shipment form."""
import os

path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\analysis.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the block from '<!-- Query Card -->' to the closing </div> before '<!-- Live Agent'
start_marker = '        <!-- Query Card -->'
end_marker   = '\n        <!-- Live Agent Reasoning -->'
start_idx = content.find(start_marker)
end_idx   = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print(f'Markers not found! start={start_idx} end={end_idx}')
    exit(1)

new_block = '''        <!-- Shipment Creation Form -->
        <div class="p-4 border-b border-white/5 flex-shrink-0 overflow-y-auto" style="max-height:56vh;">
            <div class="flex items-center gap-2 mb-3">
                <span class="material-symbols-outlined text-secondary text-lg">local_shipping</span>
                <div>
                    <h2 class="text-sm font-bold text-white">New Shipment</h2>
                    <div class="text-[10px] text-outline" id="user-role-label">Route Intelligence \u00b7 AI-powered analysis</div>
                </div>
            </div>
            <!-- UUID -->
            <div class="mb-2">
                <label class="text-[10px] font-bold uppercase tracking-wider text-outline block mb-1">Shipment ID</label>
                <div class="flex gap-1.5">
                    <input id="shipment-uuid" type="text" maxlength="36"
                        class="flex-1 bg-surface-container-highest border-none focus:ring-1 focus:ring-secondary/50 rounded-lg px-3 py-2 text-[11px] font-mono text-secondary placeholder:text-outline/40"
                        placeholder="Auto-generated"/>
                    <button type="button" onclick="genUUID()" title="Regenerate"
                        class="px-2.5 py-2 rounded-lg bg-surface-container-high border border-white/5 text-outline hover:text-secondary transition-all">
                        <span class="material-symbols-outlined text-sm">refresh</span>
                    </button>
                </div>
            </div>
            <!-- Origin & Destination -->
            <div class="grid grid-cols-1 gap-2 mb-2">
                <div>
                    <label class="text-[10px] font-bold uppercase tracking-wider text-outline block mb-1">Origin</label>
                    <input id="inp-origin" type="text"
                        class="w-full bg-surface-container-highest border-none focus:ring-1 focus:ring-secondary/50 rounded-lg px-3 py-2 text-sm text-on-surface placeholder:text-outline/40"
                        placeholder="e.g. Delhi, Mumbai, Shanghai"/>
                </div>
                <div>
                    <label class="text-[10px] font-bold uppercase tracking-wider text-outline block mb-1">Destination</label>
                    <input id="inp-dest" type="text"
                        class="w-full bg-surface-container-highest border-none focus:ring-1 focus:ring-secondary/50 rounded-lg px-3 py-2 text-sm text-on-surface placeholder:text-outline/40"
                        placeholder="e.g. Rotterdam, Kochi, Tokyo"/>
                </div>
            </div>
            <!-- Transport Mode -->
            <div class="mb-2">
                <label class="text-[10px] font-bold uppercase tracking-wider text-outline block mb-1">Mode</label>
                <div class="flex gap-1.5 route-type-row">
                    <button type="button" class="route-type-btn active flex-1" id="btn-land" onclick="setRouteType('land')">&#x1F697; Road</button>
                    <button type="button" class="route-type-btn flex-1" id="btn-sea"  onclick="setRouteType('sea')">&#x1F6A2; Sea</button>
                    <button type="button" class="route-type-btn flex-1" id="btn-air"  onclick="setRouteType('air')">&#x2708; Air</button>
                </div>
            </div>
            <!-- Cargo & Weight -->
            <div class="grid grid-cols-2 gap-2 mb-2">
                <div>
                    <label class="text-[10px] font-bold uppercase tracking-wider text-outline block mb-1">Cargo Type</label>
                    <select id="inp-cargo"
                        class="w-full bg-surface-container-highest border-none focus:ring-1 focus:ring-secondary/50 rounded-lg px-3 py-2 text-xs text-on-surface">
                        <option value="general">General</option>
                        <option value="electronics">Electronics</option>
                        <option value="perishables">Perishables</option>
                        <option value="pharmaceuticals">Pharmaceuticals</option>
                        <option value="automotive">Automotive</option>
                        <option value="chemicals">Chemicals</option>
                        <option value="bulk">Bulk</option>
                        <option value="energy">Energy</option>
                    </select>
                </div>
                <div>
                    <label class="text-[10px] font-bold uppercase tracking-wider text-outline block mb-1">Weight (kg)</label>
                    <input id="inp-weight" type="number" min="0" step="1"
                        class="w-full bg-surface-container-highest border-none focus:ring-1 focus:ring-secondary/50 rounded-lg px-3 py-2 text-xs text-on-surface placeholder:text-outline/40"
                        placeholder="e.g. 2500"/>
                </div>
            </div>
            <!-- Budget & Timeline -->
            <div class="grid grid-cols-2 gap-2 mb-3">
                <div>
                    <label class="text-[10px] font-bold uppercase tracking-wider text-outline block mb-1">Budget (USD)</label>
                    <div class="relative">
                        <span class="absolute left-2.5 top-1/2 -translate-y-1/2 text-outline text-[10px]">$</span>
                        <input id="inp-budget" type="number" min="0" step="100"
                            class="w-full bg-surface-container-highest border-none focus:ring-1 focus:ring-secondary/50 rounded-lg pl-5 pr-3 py-2 text-xs text-on-surface placeholder:text-outline/40"
                            placeholder="e.g. 50000"/>
                    </div>
                </div>
                <div>
                    <label class="text-[10px] font-bold uppercase tracking-wider text-outline block mb-1">Timeline (days)</label>
                    <input id="inp-eta" type="number" min="1" max="365"
                        class="w-full bg-surface-container-highest border-none focus:ring-1 focus:ring-secondary/50 rounded-lg px-3 py-2 text-xs text-on-surface placeholder:text-outline/40"
                        placeholder="Auto (OSRM)"/>
                </div>
            </div>
            <!-- Quick Examples -->
            <div class="flex flex-wrap gap-1.5 mb-3" id="example-chips">
                <button type="button" class="example-chip india" id="ex1">&#x1F1EE;&#x1F1F3; Delhi&#x2192;Kerala</button>
                <button type="button" class="example-chip india" id="ex2">&#x1F1EE;&#x1F1F3; Mumbai&#x2192;BLR</button>
                <button type="button" class="example-chip" id="ex3">&#x1F30A; Shanghai&#x2192;RTM</button>
            </div>
            <!-- Error -->
            <div id="form-error" class="hidden mb-2 text-xs text-error bg-error/10 border border-error/20 rounded-lg px-3 py-2"></div>
            <form id="analysis-form" onsubmit="return false;">
                <textarea id="query-input" class="hidden"></textarea>
                <button type="submit" id="analyze-btn" class="btn-analyze kinetic-gradient text-white">
                    <span id="btn-text">&#x26A1; Analyse &amp; Simulate Route</span>
                    <span id="btn-spinner" class="spin-ring hidden"></span>
                </button>
            </form>
        </div>
'''

content = content[:start_idx] + new_block + content[end_idx:]

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('SUCCESS: analysis.html patched')
