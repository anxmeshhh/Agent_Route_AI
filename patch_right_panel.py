"""
Replace the ENTIRE right panel (lines 498-729) of analysis.html with a clean
3-tab structure: Normal (ticket board + results), Threat Induce, Suggestions.
The 3 tabs are ALWAYS visible at the top of the right panel.
"""
path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\analysis.html'
with open(path, encoding='utf-8') as f:
    lines = f.readlines()

# Lines 498-729 (0-indexed: 497-728) = entire right <aside>
new_right_panel = r"""    <!-- RIGHT PANEL: 3-MODE ANALYSIS -->
    <aside class="w-[340px] flex-shrink-0 flex flex-col border-l border-white/5 bg-surface-container-low overflow-hidden">

        <!-- ═══ TOP-LEVEL 3-MODE TABS (ALWAYS VISIBLE) ═══ -->
        <div class="flex gap-1 px-3 pt-3 pb-2 border-b border-white/5 flex-shrink-0">
            <button class="sim-mode-tab active" onclick="switchSimMode('normal',this)" id="simtab-normal">
                <span class="material-symbols-outlined text-xs mr-0.5">route</span> Normal
            </button>
            <button class="sim-mode-tab" onclick="switchSimMode('threat',this)" id="simtab-threat">
                <span class="text-xs mr-0.5">⚡</span> Threat
            </button>
            <button class="sim-mode-tab" onclick="switchSimMode('suggest',this)" id="simtab-suggest">
                <span class="text-xs mr-0.5">💡</span> Suggestions
            </button>
        </div>

        <!-- ════════════════════════════════════════════════ -->
        <!-- MODE: NORMAL — Ticket Board + Analysis Results  -->
        <!-- ════════════════════════════════════════════════ -->
        <div class="flex-1 flex flex-col overflow-hidden" id="sim-mode-normal">

            <!-- Ticket Board -->
            <div class="flex flex-col flex-1 overflow-hidden" id="ticket-board-panel">
                <!-- Board Header -->
                <div class="px-3 pt-2 pb-1.5 border-b border-white/5 flex-shrink-0">
                    <div class="flex items-center justify-between mb-1.5">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-secondary text-sm">confirmation_number</span>
                            <h2 class="text-[10px] font-bold text-white uppercase tracking-wider">Ticket Board</h2>
                            <span class="text-[9px] font-mono text-secondary bg-secondary/10 px-1.5 rounded" id="open-ticket-count">0 open</span>
                        </div>
                        <div class="flex items-center gap-1">
                            <span class="text-[9px] text-outline font-mono" id="board-shipment-uuid">—</span>
                            <button type="button" onclick="loadTickets()" class="text-slate-500 hover:text-white" title="Refresh">
                                <span class="material-symbols-outlined text-sm">refresh</span>
                            </button>
                        </div>
                    </div>
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
                    <div class="text-center py-8 text-outline text-xs" id="ticket-empty-state">
                        <span class="material-symbols-outlined text-3xl block mb-2 opacity-40">confirmation_number</span>
                        Fill the shipment form and click<br>
                        <strong class="text-secondary">🎫 Create Ticket</strong> to get started
                    </div>
                </div>
            </div>

            <!-- Analysis Results (hidden until ticket analysis runs) -->
            <div class="hidden flex-1 flex flex-col overflow-hidden" id="results-state">
                <!-- Ticket ref header -->
                <div class="px-3 pt-1.5 pb-1 border-b border-white/5 flex items-center gap-2 flex-shrink-0">
                    <button onclick="backToBoard()" class="text-secondary text-[10px] font-bold hover:text-white transition-colors">← Board</button>
                    <span class="text-[9px] font-mono text-primary bg-primary/10 px-2 py-0.5 rounded" id="result-ticket-id">—</span>
                    <span class="text-[10px] text-outline truncate flex-1" id="result-ticket-title">—</span>
                </div>
                <!-- Sub-tabs: Risk / Intel / Factors / Decision / Routes -->
                <div class="flex gap-1 px-3 pt-1.5 pb-1.5 border-b border-white/5 overflow-x-auto flex-shrink-0" id="result-tabs">
                    <button class="result-tab active" onclick="switchTab('risk')">Risk</button>
                    <button class="result-tab" onclick="switchTab('intel')">Intel</button>
                    <button class="result-tab" onclick="switchTab('factors')">Factors</button>
                    <button class="result-tab" onclick="switchTab('decision')">Decision</button>
                    <button class="result-tab" onclick="switchTab('routes')">Routes</button>
                </div>
                <!-- Tab Content -->
                <div class="flex-1 overflow-y-auto p-3 space-y-3">
                    <!-- TAB: Risk Assessment -->
                    <div class="tab-pane active" id="tab-risk">
                        <div class="glass-panel p-4 rounded-xl border border-white/5">
                            <div class="flex items-center justify-between mb-3">
                                <div class="flex items-center gap-2">
                                    <span class="material-symbols-outlined text-secondary">shield</span>
                                    <h2 class="text-sm font-bold text-white">Risk Assessment</h2>
                                </div>
                                <span class="risk-pill" id="risk-level-badge" style="background:rgba(255,255,255,0.05);color:#757480;">--</span>
                            </div>
                            <div class="mb-3"><div class="risk-bar bg-surface-container-highest rounded-full h-2.5 overflow-hidden"><div class="h-full rounded-full transition-all duration-1000" id="risk-bar-fill" style="width:0;background:#757480"></div></div></div>
                            <div class="grid grid-cols-2 gap-2 mb-3">
                                <div class="stat-card"><div class="stat-label">Risk Score</div><div class="stat-value" id="risk-score-val">—</div></div>
                                <div class="stat-card"><div class="stat-label">ETA</div><div class="stat-value" id="eta-val">—</div></div>
                                <div class="stat-card"><div class="stat-label">Cost</div><div class="stat-value" id="cost-val">—</div></div>
                                <div class="stat-card"><div class="stat-label">Plan</div><div class="stat-value" id="plan-val">—</div></div>
                            </div>
                            <div class="text-xs text-on-surface-variant leading-relaxed" id="risk-reasoning">Run analysis to see risk assessment.</div>
                        </div>
                    </div>
                    <!-- TAB: Intel -->
                    <div class="tab-pane" id="tab-intel">
                        <div class="glass-panel p-4 rounded-xl border border-white/5">
                            <div class="flex items-center gap-2 mb-3"><span class="material-symbols-outlined text-primary">newspaper</span><h2 class="text-sm font-bold text-white">Intelligence Feed</h2></div>
                            <div id="intel-content" class="text-xs text-on-surface-variant leading-relaxed">No intelligence data yet.</div>
                        </div>
                    </div>
                    <!-- TAB: Factors -->
                    <div class="tab-pane" id="tab-factors">
                        <div class="glass-panel p-4 rounded-xl border border-white/5">
                            <div class="flex items-center gap-2 mb-3"><span class="material-symbols-outlined text-tertiary">tune</span><h2 class="text-sm font-bold text-white">Risk Factors</h2></div>
                            <div id="factors-content" class="space-y-2 text-xs">No factors data yet.</div>
                        </div>
                    </div>
                    <!-- TAB: Decision -->
                    <div class="tab-pane" id="tab-decision">
                        <div class="glass-panel p-4 rounded-xl border border-white/5">
                            <div class="flex items-center gap-2 mb-3"><span class="material-symbols-outlined text-secondary">psychology</span><h2 class="text-sm font-bold text-white">AI Decision</h2></div>
                            <div id="decision-content" class="text-xs text-on-surface-variant leading-relaxed">No decision yet.</div>
                        </div>
                    </div>
                    <!-- TAB: Routes -->
                    <div class="tab-pane" id="tab-routes">
                        <div class="glass-panel p-4 rounded-xl border border-white/5 hidden" id="alt-route-comparison">
                            <h3 class="text-sm font-bold text-white mb-3">Route Comparison</h3>
                            <div id="alt-route-comparison-content" class="text-xs"></div>
                        </div>
                        <div class="text-center py-8 text-outline text-xs" id="no-routes-msg">Run an analysis to see route comparisons</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- ════════════════════════════════════════════════ -->
        <!-- MODE: THREAT INDUCE                             -->
        <!-- ════════════════════════════════════════════════ -->
        <div class="flex-1 flex flex-col overflow-hidden hidden" id="sim-mode-threat">
            <div class="flex-1 overflow-y-auto p-3">
                <!-- Threat controls -->
                <div class="glass-panel p-3 rounded-xl border border-white/5 mb-3">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="text-sm">⚠️</span>
                        <h3 class="text-xs font-bold text-white uppercase tracking-wider">Threat Simulation</h3>
                    </div>
                    <p class="text-[10px] text-outline mb-3">Groq AI generates a realistic mid-route disruption for the active ticket's route.</p>
                    <div class="flex gap-2">
                        <button class="flex-1 py-2.5 rounded-lg text-xs font-bold text-white border-none cursor-pointer transition-all"
                            style="background:linear-gradient(135deg,#7f1d1d,#ff1f3d);box-shadow:0 4px 16px rgba(255,31,61,0.3)"
                            id="btn-induce-threat" onclick="induceThreatFromPanel()">
                            ⚡ Induce Random Threat
                        </button>
                        <button class="py-2 px-3 rounded-lg text-xs font-bold border cursor-pointer"
                            style="background:transparent;border-color:rgba(255,255,255,0.1);color:#757480"
                            onclick="clearThreat()">✕</button>
                    </div>
                </div>
                <!-- Active ticket info -->
                <div class="mb-3 px-1">
                    <div class="flex items-center gap-2">
                        <span class="text-[9px] font-mono text-primary bg-primary/10 px-2 py-0.5 rounded" id="threat-ticket-id">—</span>
                        <span class="text-[10px] text-outline" id="threat-ticket-route">Select a ticket first</span>
                    </div>
                </div>
                <!-- Threat display area -->
                <div id="threat-display-panel">
                    <div class="text-center py-10">
                        <span class="text-4xl block mb-3 opacity-30">⚠️</span>
                        <div class="text-xs text-outline mb-1">Click <strong class="text-[#ff6e84]">⚡ Induce Random Threat</strong></div>
                        <div class="text-[10px] text-outline">Simulates: piracy, storm, port closure, fire, collision, strike…</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- ════════════════════════════════════════════════ -->
        <!-- MODE: SUGGESTIONS & REROUTING                   -->
        <!-- ════════════════════════════════════════════════ -->
        <div class="flex-1 flex flex-col overflow-hidden hidden" id="sim-mode-suggest">
            <div class="flex-1 overflow-y-auto p-3">
                <!-- Reroute controls -->
                <div class="glass-panel p-3 rounded-xl border border-white/5 mb-3">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="text-sm">🔀</span>
                        <h3 class="text-xs font-bold text-white uppercase tracking-wider">Smart Rerouting</h3>
                    </div>
                    <p class="text-[10px] text-outline mb-3">AI generates 4 alternative routes avoiding the threat zone, with cost/time/risk comparison.</p>
                    <button class="w-full py-2.5 rounded-lg text-xs font-bold text-white border-none cursor-pointer transition-all"
                        style="background:linear-gradient(135deg,#0c3577,#0066ff);box-shadow:0 4px 16px rgba(0,102,255,0.3)"
                        id="btn-gen-reroutes" onclick="genReroutesFromPanel()">
                        🔀 Generate Alternative Routes
                    </button>
                </div>
                <!-- Weather bar -->
                <div id="weather-bar-display" class="hidden mb-3"></div>
                <!-- Recommendation banner -->
                <div id="recommendation-banner" class="hidden mb-3"></div>
                <!-- Reroute cards -->
                <div id="reroute-cards-display">
                    <div class="text-center py-10">
                        <span class="text-4xl block mb-3 opacity-30">🔀</span>
                        <div class="text-xs text-outline mb-1">First induce a threat in the <strong class="text-[#ff6e84]">⚡ Threat</strong> tab</div>
                        <div class="text-[10px] text-outline">Then generate reroutes to see alternatives with cost, time, risk analysis</div>
                    </div>
                </div>
            </div>
        </div>

    </aside>
"""

# Replace lines 498-729 (0-indexed: 497-728)
lines[497:728] = [new_right_panel]

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print(f"Right panel replaced (lines 498-729 -> new clean structure)")
