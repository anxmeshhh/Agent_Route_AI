"""Replace lines 679-681 in analysis.html to add threat + suggestion panels."""
path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\analysis.html'
with open(path, encoding='utf-8') as f:
    lines = f.readlines()

# Lines 679-681 (0-indexed: 678-680) are:
# 679:             </div>       <- closes tab content scrollable
# 680:         </div>           <- closes results-state
# 681:     </aside>             <- closes aside

new_block = """            </div>
            </div> <!-- /sim-mode-normal content -->
            </div> <!-- /sim-mode-normal -->

            <!-- ═══ MODE: THREAT INDUCE ═══ -->
            <div class="flex-1 flex flex-col overflow-hidden hidden" id="sim-mode-threat">
                <div class="flex-1 overflow-y-auto p-3">
                    <!-- Threat controls -->
                    <div class="glass-panel p-3 rounded-xl border border-white/5 mb-3">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-sm">⚠️</span>
                            <h3 class="text-xs font-bold text-white uppercase tracking-wider">Threat Simulation</h3>
                            <span class="text-[9px] text-outline">Groq AI generates a realistic mid-route disruption</span>
                        </div>
                        <div class="flex gap-2">
                            <button class="flex-1 py-2 rounded-lg text-xs font-bold text-white border-none cursor-pointer transition-all"
                                style="background:linear-gradient(135deg,#7f1d1d,#ff1f3d);box-shadow:0 4px 16px rgba(255,31,61,0.3)"
                                id="btn-induce-threat" onclick="induceThreatFromPanel()">
                                ⚡ Induce Random Threat
                            </button>
                            <button class="py-2 px-3 rounded-lg text-xs font-bold border cursor-pointer transition-all"
                                style="background:transparent;border-color:rgba(255,255,255,0.1);color:#757480"
                                onclick="clearThreat()">✕ Clear</button>
                        </div>
                    </div>
                    <!-- Threat display area -->
                    <div id="threat-display-panel">
                        <div class="text-center py-10">
                            <span class="text-3xl block mb-2 opacity-30">⚠️</span>
                            <div class="text-xs text-outline">Click <strong class="text-[#ff6e84]">⚡ Induce Random Threat</strong></div>
                            <div class="text-[10px] text-outline mt-1">to simulate a piracy, storm, port closure, or other disruption</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ═══ MODE: SUGGESTIONS & REROUTING ═══ -->
            <div class="flex-1 flex flex-col overflow-hidden hidden" id="sim-mode-suggest">
                <div class="flex-1 overflow-y-auto p-3">
                    <!-- Reroute controls -->
                    <div class="glass-panel p-3 rounded-xl border border-white/5 mb-3">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-sm">🔀</span>
                            <h3 class="text-xs font-bold text-white uppercase tracking-wider">Smart Rerouting</h3>
                            <span class="text-[9px] text-outline">AI-generated alternative routes avoiding the threat zone</span>
                        </div>
                        <button class="w-full py-2 rounded-lg text-xs font-bold text-white border-none cursor-pointer transition-all"
                            style="background:linear-gradient(135deg,#0c3577,#0066ff);box-shadow:0 4px 16px rgba(0,102,255,0.3)"
                            id="btn-gen-reroutes" onclick="genReroutesFromPanel()">
                            🔀 Generate Alternative Routes & Suggestions
                        </button>
                    </div>
                    <!-- Weather bar -->
                    <div id="weather-bar-display" class="hidden mb-3"></div>
                    <!-- Recommendation banner -->
                    <div id="recommendation-banner" class="hidden mb-3"></div>
                    <!-- Reroute cards -->
                    <div id="reroute-cards-display">
                        <div class="text-center py-10">
                            <span class="text-3xl block mb-2 opacity-30">🔀</span>
                            <div class="text-xs text-outline">First induce a threat, then generate reroutes</div>
                            <div class="text-[10px] text-outline mt-1">to see alternative routes with cost, time, risk analysis</div>
                        </div>
                    </div>
                </div>
            </div>

        </div> <!-- /results-state -->
    </aside>
"""

# Replace lines 679-681 (0-indexed 678-680)
lines[678:681] = [new_block]

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("Threat + Suggestions panels injected.")
