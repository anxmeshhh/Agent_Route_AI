"""
Patch analysis.html:
1. Replace submit button text with 'Create Ticket'
2. Replace the right-panel 'brand-panel' with a ticket board
3. Keep results panel intact for when analysis runs
"""
path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\analysis.html'
with open(path, 'r', encoding='utf-8') as f:
    html = f.read()

# ── 1. Replace button text ─────────────────────────────────────────
html = html.replace(
    '&#x26A1; Analyse &amp; Simulate Route',
    '&#x1F3AB; Create Ticket'
)

# ── 2. Inject ticket board CSS before </style> ────────────────────
ticket_css = '''
    /* Ticket system */
    .ticket-card { padding:10px 12px; border-radius:10px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07); margin-bottom:8px; cursor:pointer; transition:all 0.2s; }
    .ticket-card:hover { background:rgba(255,255,255,0.06); border-color:rgba(0,217,255,0.2); }
    .ticket-card.selected { border-color:rgba(0,217,255,0.4); background:rgba(0,217,255,0.06); }
    .tkt-id { font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:700; color:#00d9ff; }
    .tkt-title { font-size:12px; font-weight:600; color:#f1effd; margin:3px 0; line-height:1.3; }
    .tkt-meta { font-size:10px; color:#abaab7; display:flex; flex-wrap:wrap; gap:6px; margin-top:4px; }
    .tkt-status { font-size:9px; font-weight:700; padding:1px 7px; border-radius:3px; text-transform:uppercase; letter-spacing:.05em; }
    .s-open        { background:rgba(117,116,128,0.2); color:#abaab7; }
    .s-in_progress { background:rgba(0,217,255,0.15);  color:#00d9ff; }
    .s-completed   { background:rgba(74,222,128,0.15); color:#4ade80; }
    .s-failed      { background:rgba(255,110,132,0.15);color:#ff6e84; }
    .s-closed      { background:rgba(255,255,255,0.05);color:#757480; }
    .tkt-priority { font-size:9px; font-weight:700; padding:1px 6px; border-radius:3px; text-transform:uppercase; }
    .p-critical { color:#ff6e84; background:rgba(255,110,132,0.12); }
    .p-high     { color:#ffb148; background:rgba(255,177,72,0.12); }
    .p-medium   { color:#facc15; background:rgba(250,204,21,0.10); }
    .p-low      { color:#4ade80; background:rgba(74,222,128,0.10); }
    .btn-run-analysis { padding:5px 12px; border-radius:6px; font-size:10px; font-weight:700; background:rgba(0,217,255,0.15); color:#00d9ff; border:1px solid rgba(0,217,255,0.3); cursor:pointer; transition:all .2s; white-space:nowrap; }
    .btn-run-analysis:hover { background:rgba(0,217,255,0.25); }
    .btn-close-ticket { padding:4px 10px; border-radius:6px; font-size:10px; font-weight:700; background:rgba(255,255,255,0.05); color:#757480; border:1px solid rgba(255,255,255,0.08); cursor:pointer; }
    .ticket-filter-btn { padding:3px 10px; border-radius:4px; font-size:9px; font-weight:700; background:transparent; border:1px solid rgba(255,255,255,0.08); color:#757480; cursor:pointer; transition:all .15s; }
    .ticket-filter-btn.active { background:rgba(0,217,255,0.12); border-color:rgba(0,217,255,0.3); color:#00d9ff; }
    .pulse-dot { width:7px; height:7px; border-radius:50%; background:#00d9ff; display:inline-block; animation:pulse-anim 1.2s ease-in-out infinite; }
    @keyframes pulse-anim { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.7)} }
'''
html = html.replace('</style>', ticket_css + '</style>', 1)

# ── 3. Replace the brand-panel with the ticket board ──────────────
old_brand = '''        <!-- Brand panel (shown before results) -->
        <div class="flex-1 flex flex-col items-center justify-center p-6 text-center" id="brand-panel">
            <div class="text-5xl mb-4">🗺</div>
            <h1 class="text-xl font-bold text-white mb-1">AgentRoute<span class="text-primary">AI</span></h1>
            <div class="text-xs text-outline mb-4">8-Agent Agentic Route Intelligence</div>
            <div class="flex flex-wrap gap-1.5 justify-center mb-4">
                <span class="text-[9px] px-2 py-0.5 rounded bg-secondary/10 text-secondary border border-secondary/20">📦 Intake</span>
                <span class="text-[9px] px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">🌤 Weather</span>
                <span class="text-[9px] px-2 py-0.5 rounded bg-tertiary/10 text-tertiary border border-tertiary/20">📰 News</span>
                <span class="text-[9px] px-2 py-0.5 rounded bg-secondary/10 text-secondary border border-secondary/20">📊 Historical</span>
                <span class="text-[9px] px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">🚗 Vehicle</span>
                <span class="text-[9px] px-2 py-0.5 rounded bg-tertiary/10 text-tertiary border border-tertiary/20">📍 Intel</span>
                <span class="text-[9px] px-2 py-0.5 rounded bg-secondary/10 text-secondary border border-secondary/20">🌍 Geo</span>
            </div>
            <div class="text-[9px] px-3 py-1 rounded kinetic-gradient text-white font-bold mb-3">⚡ LLM Brain</div>
            <div class="text-[10px] text-outline">Try <strong class="text-secondary">Delhi → Kerala</strong> or <strong class="text-primary">Shanghai → Rotterdam</strong></div>
        </div>'''

new_ticket_board = '''        <!-- Ticket Board (default right panel) -->
        <div class="flex flex-col h-full" id="ticket-board-panel">
            <!-- Board Header -->
            <div class="px-3 pt-3 pb-2 border-b border-white/5 flex-shrink-0">
                <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-secondary text-sm">confirmation_number</span>
                        <h2 class="text-xs font-bold text-white uppercase tracking-wider">Ticket Board</h2>
                        <span class="text-[10px] font-mono text-secondary bg-secondary/10 px-2 rounded" id="open-ticket-count">0 open</span>
                    </div>
                    <div class="flex items-center gap-1">
                        <span class="text-[10px] text-outline font-mono" id="board-shipment-uuid">—</span>
                        <button type="button" onclick="loadTickets()" class="text-slate-500 hover:text-white" title="Refresh">
                            <span class="material-symbols-outlined text-sm">refresh</span>
                        </button>
                    </div>
                </div>
                <!-- Filters -->
                <div class="flex gap-1 flex-wrap">
                    <button class="ticket-filter-btn active" onclick="filterTickets('all',this)">All</button>
                    <button class="ticket-filter-btn" onclick="filterTickets('open',this)">Open</button>
                    <button class="ticket-filter-btn" onclick="filterTickets('in_progress',this)">Running</button>
                    <button class="ticket-filter-btn" onclick="filterTickets('completed',this)">Done</button>
                    <button class="ticket-filter-btn" onclick="filterTickets('closed',this)">Closed</button>
                </div>
            </div>
            <!-- Ticket List -->
            <div class="flex-1 overflow-y-auto p-3" id="ticket-list">
                <div class="text-center py-10 text-outline text-xs" id="ticket-empty-state">
                    <span class="material-symbols-outlined text-3xl block mb-2 opacity-40">confirmation_number</span>
                    Fill the shipment form and click<br>
                    <strong class="text-secondary">🎫 Create Ticket</strong> to get started
                </div>
            </div>
        </div>'''

if old_brand in html:
    html = html.replace(old_brand, new_ticket_board, 1)
    print("Brand panel replaced with ticket board ✅")
else:
    # Try to find it via markers
    idx = html.find('id="brand-panel"')
    if idx != -1:
        # find enclosing div start
        start = html.rfind('<div', 0, idx)
        # find its closing </div> — count nesting
        depth = 0
        i = start
        while i < len(html):
            if html[i:i+4] == '<div':
                depth += 1
            elif html[i:i+6] == '</div>':
                depth -= 1
                if depth == 0:
                    html = html[:start] + new_ticket_board + html[i+6:]
                    print("Brand panel replaced via fallback ✅")
                    break
            i += 1
    else:
        print("WARNING: brand-panel not found, skipping replacement")

with open(path, 'w', encoding='utf-8') as f:
    f.write(html)
print("analysis.html patched.")
