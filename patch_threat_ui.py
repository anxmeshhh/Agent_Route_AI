"""
Patch analysis.html:
1. Add ⚡ Threat + 🔀 Reroute buttons on completed ticket cards
2. Add threat display + reroute display panels below the ticket board
"""
path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\analysis.html'
with open(path, encoding='utf-8') as f:
    html = f.read()

# ── 1. Add CSS for threat cards ─────────────────────────────────
threat_css = '''
    /* Threat System */
    .threat-card-panel { padding:14px; border-radius:12px; border:1px solid; margin-top:8px; animation: slideIn .4s ease; }
    .threat-CRITICAL { background:rgba(127,29,29,0.25); border-color:#7f1d1d; }
    .threat-HIGH     { background:rgba(220,38,38,0.15); border-color:#dc2626; }
    .threat-MEDIUM   { background:rgba(239,68,68,0.1);  border-color:#ef4444; }
    .threat-LOW      { background:rgba(245,158,11,0.1); border-color:#f59e0b; }
    .threat-badge2 { font-size:9px; font-weight:700; padding:2px 8px; border-radius:3px; text-transform:uppercase; letter-spacing:.5px; }
    .tb-CRITICAL { background:rgba(127,29,29,0.6); color:#fca5a5; }
    .tb-HIGH     { background:rgba(220,38,38,0.4); color:#fca5a5; }
    .tb-MEDIUM   { background:rgba(239,68,68,0.3); color:#fcd34d; }
    .tb-LOW      { background:rgba(245,158,11,0.2); color:#fde68a; }
    .reroute-card { padding:12px; border-radius:10px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07); margin-bottom:6px; transition:all .2s; }
    .reroute-card:hover { background:rgba(255,255,255,0.06); }
    .reroute-card.rec { border-color:rgba(74,222,128,0.3); background:rgba(74,222,128,0.06); }
    .rec-badge { font-size:8px; padding:1px 6px; border-radius:3px; background:rgba(74,222,128,0.15); color:#4ade80; font-weight:700; text-transform:uppercase; }
    .mode-badge { font-size:8px; padding:1px 6px; border-radius:3px; font-weight:700; text-transform:uppercase; }
    .mode-AIR        { background:rgba(0,102,255,0.2); color:#93c5fd; }
    .mode-SEA        { background:rgba(0,212,255,0.15); color:#00d9ff; }
    .mode-MULTIMODAL { background:rgba(139,92,246,0.2); color:#c4b5fd; }
    .sim-panel-tabs { display:flex; gap:4px; margin-bottom:8px; }
    .sim-tab { padding:5px 12px; border-radius:6px; font-size:10px; font-weight:700; border:1px solid rgba(255,255,255,0.08); background:transparent; color:#757480; cursor:pointer; transition:all .15s; }
    .sim-tab.active { background:rgba(0,217,255,0.12); border-color:rgba(0,217,255,0.3); color:#00d9ff; }
    .sim-tab.threat-tab.active { background:rgba(255,31,61,0.12); border-color:rgba(255,31,61,0.3); color:#ff6e84; }
    .sim-tab.suggest-tab.active { background:rgba(74,222,128,0.12); border-color:rgba(74,222,128,0.3); color:#4ade80; }
    .threat-btn-sm { padding:4px 10px; border-radius:5px; font-size:9px; font-weight:700; border:1px solid rgba(255,31,61,0.3); background:rgba(255,31,61,0.1); color:#ff6e84; cursor:pointer; transition:all .15s; white-space:nowrap; }
    .threat-btn-sm:hover { background:rgba(255,31,61,0.2); }
    .reroute-btn-sm { padding:4px 10px; border-radius:5px; font-size:9px; font-weight:700; border:1px solid rgba(0,102,255,0.3); background:rgba(0,102,255,0.1); color:#93c5fd; cursor:pointer; transition:all .15s; white-space:nowrap; }
    .reroute-btn-sm:hover { background:rgba(0,102,255,0.2); }
    @keyframes slideIn { from{opacity:0;transform:translateY(10px);} to{opacity:1;transform:translateY(0);} }
'''
html = html.replace('</style>', threat_css + '</style>', 1)

# ── 2. Add threat/reroute display panels after ticket-list div ──
# Find the closing of ticket-list div, we insert after it
insertion_marker = '<!-- Error -->'
threat_panels = '''<!-- Threat & Suggestion Display (below ticket cards) -->
            <div id="sim-panels" class="hidden" style="border-top:1px solid rgba(255,255,255,0.05);padding-top:10px;margin-top:4px;">
                <!-- Panel tabs -->
                <div class="sim-panel-tabs">
                    <button class="sim-tab active" onclick="switchSimPanel('normal',this)">📊 Normal</button>
                    <button class="sim-tab threat-tab" onclick="switchSimPanel('threat',this)">⚡ Threat</button>
                    <button class="sim-tab suggest-tab" onclick="switchSimPanel('suggest',this)">💡 Suggestions</button>
                </div>
                <!-- Normal panel (shows basic ticket analysis) -->
                <div id="sim-normal" class="sim-panel">
                    <div class="text-[10px] text-outline mb-2">Run ▶ on a ticket to see normal route analysis results in the right panel.</div>
                </div>
                <!-- Threat panel -->
                <div id="sim-threat" class="sim-panel hidden">
                    <div id="threat-display" class="text-center py-4 text-outline text-[10px]">
                        Click <strong class="text-[#ff6e84]">⚡ Induce Threat</strong> on a completed ticket to simulate a disruption.
                    </div>
                </div>
                <!-- Suggestions panel -->
                <div id="sim-suggest" class="sim-panel hidden">
                    <div id="reroute-display" class="text-center py-4 text-outline text-[10px]">
                        After inducing a threat, click <strong class="text-[#93c5fd]">🔀 Reroute</strong> to see alternative routes with cost/time/risk analysis.
                    </div>
                </div>
            </div>
            '''
html = html.replace(insertion_marker, threat_panels + '\n            ' + insertion_marker, 1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(html)
print("Threat panels + CSS injected into analysis.html")
