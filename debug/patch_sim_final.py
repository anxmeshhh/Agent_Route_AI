"""Add sim-mode-tab CSS and switchSimMode + panel JS functions to analysis.html."""
path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\analysis.html'
with open(path, encoding='utf-8') as f:
    html = f.read()

# 1. CSS for sim-mode-tab
sim_css = '''
    /* Simulation mode tabs */
    .sim-mode-tab { display:inline-flex; align-items:center; gap:2px; padding:5px 10px; border-radius:6px; font-size:10px; font-weight:700; border:1px solid rgba(255,255,255,0.08); background:transparent; color:#757480; cursor:pointer; transition:all .15s; }
    .sim-mode-tab:hover { border-color:rgba(255,255,255,0.15); color:#aaa; }
    .sim-mode-tab.active { background:rgba(0,217,255,0.1); border-color:rgba(0,217,255,0.3); color:#00d9ff; }
    #simtab-threat.active { background:rgba(255,31,61,0.1); border-color:rgba(255,31,61,0.3); color:#ff6e84; }
    #simtab-suggest.active { background:rgba(74,222,128,0.1); border-color:rgba(74,222,128,0.3); color:#4ade80; }
'''
html = html.replace('</style>', sim_css + '</style>', 1)

# 2. JS functions — add before the TICKET SYSTEM block's closing </script>
import re
match = re.search(r'(function _timeAgo\(dtStr\).*?}\s*\n)', html, re.DOTALL)
if not match:
    print("ERROR: could not find _timeAgo function")
else:
    insert_pos = match.end()
    sim_js = r"""
// ── Simulation Mode Switching ──────────────────────────
function switchSimMode(mode, btn) {
    document.querySelectorAll('.sim-mode-tab').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    document.getElementById('sim-mode-normal')?.classList.add('hidden');
    document.getElementById('sim-mode-threat')?.classList.add('hidden');
    document.getElementById('sim-mode-suggest')?.classList.add('hidden');
    document.getElementById('sim-mode-' + mode)?.classList.remove('hidden');
}

// ── Clear threat ──────────────────────────────────────
function clearThreat() {
    _currentThreat = null;
    document.getElementById('threat-display-panel').innerHTML = `
        <div class="text-center py-10">
            <span class="text-3xl block mb-2 opacity-30">⚠️</span>
            <div class="text-xs text-outline">Click <strong class="text-[#ff6e84]">⚡ Induce Random Threat</strong></div>
            <div class="text-[10px] text-outline mt-1">to simulate a piracy, storm, port closure, or other disruption</div>
        </div>`;
    document.getElementById('reroute-cards-display').innerHTML = `
        <div class="text-center py-10">
            <span class="text-3xl block mb-2 opacity-30">🔀</span>
            <div class="text-xs text-outline">First induce a threat, then generate reroutes</div>
        </div>`;
    document.getElementById('weather-bar-display')?.classList.add('hidden');
    document.getElementById('recommendation-banner')?.classList.add('hidden');
}

// ── Induce threat from the panel button ──────────────
async function induceThreatFromPanel() {
    if (!_activeTicket) { alert('Select a ticket first by running analysis on it.'); return; }
    const ticketId = _activeTicket;
    const btn = document.getElementById('btn-induce-threat');
    const display = document.getElementById('threat-display-panel');

    btn.disabled = true;
    btn.textContent = '⚡ Generating…';
    display.innerHTML = '<div class="flex items-center gap-2 justify-center py-6"><span class="pulse-dot"></span><span class="text-[10px] text-[#ff6e84]">Groq AI generating threat intelligence…</span></div>';

    try {
        const r = await fetch(`/api/tickets/${ticketId}/threat`, {
            method:'POST', credentials:'include'
        });
        const data = await r.json();
        if (!r.ok || !data.success) {
            display.innerHTML = '<div class="text-xs text-error p-3">Error: ' + (data.error||'Failed') + '</div>';
            return;
        }
        _currentThreat = data.threat;
        renderThreatCard(data.threat, display);
    } catch(e) {
        display.innerHTML = '<div class="text-xs text-error p-3">Network error: ' + e.message + '</div>';
    } finally {
        btn.disabled = false;
        btn.textContent = '⚡ Induce Random Threat';
    }
}

// ── Generate reroutes from the panel button ──────────
async function genReroutesFromPanel() {
    if (!_activeTicket) { alert('Select a ticket first.'); return; }
    if (!_currentThreat) { alert('Induce a threat first in the Threat tab.'); return; }

    const ticketId = _activeTicket;
    const btn = document.getElementById('btn-gen-reroutes');
    const cardsDisplay = document.getElementById('reroute-cards-display');
    const wxBar = document.getElementById('weather-bar-display');
    const recBanner = document.getElementById('recommendation-banner');

    btn.disabled = true;
    btn.textContent = '🔀 Generating…';
    cardsDisplay.innerHTML = '<div class="flex items-center gap-2 justify-center py-6"><span class="pulse-dot"></span><span class="text-[10px] text-[#93c5fd]">Groq AI generating alternative routes…</span></div>';

    try {
        const r = await fetch(`/api/tickets/${ticketId}/reroute`, {
            method:'POST', credentials:'include',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({threat: _currentThreat})
        });
        const data = await r.json();
        if (!r.ok || !data.success) {
            cardsDisplay.innerHTML = '<div class="text-xs text-error p-3">Error: ' + (data.error||'Failed') + '</div>';
            return;
        }

        // Render weather bar
        if (data.weather) {
            const w = data.weather;
            const outlookColor = {CLEAR:'#4ade80',MODERATE:'#fde68a',ROUGH:'#fca5a5',SEVERE:'#ff6e84'}[w.overall_outlook]||'#aaa';
            wxBar.classList.remove('hidden');
            wxBar.innerHTML = `
                <div class="glass-panel p-2.5 rounded-lg border border-white/5 flex items-center gap-2 flex-wrap">
                    <span>🌤</span>
                    <span class="text-[9px] font-mono text-outline uppercase">Weather</span>
                    <span class="text-[10px] font-bold" style="color:${outlookColor}">${w.overall_outlook||'—'}</span>
                    <span class="text-[10px] text-outline flex-1">${_esc(w.summary||'')}</span>
                </div>`;
        }

        // Render recommendation banner
        const rec = data.final_recommendation;
        if (rec) {
            recBanner.classList.remove('hidden');
            recBanner.innerHTML = `
                <div class="p-3 rounded-lg" style="background:rgba(74,222,128,0.06);border:1px solid rgba(74,222,128,0.2)">
                    <div class="flex items-center gap-2 mb-1">
                        <span>🏆</span>
                        <span class="text-[10px] font-bold text-[#4ade80] uppercase">Best Route: ${_esc(rec.label||rec.route_id)}</span>
                        <span class="mode-badge mode-${rec.mode||'SEA'}">${rec.mode||''}</span>
                    </div>
                    <div class="text-[10px] text-[#c8dff5]">${_esc(rec.reason||'')}</div>
                </div>`;
        }

        // Render route cards
        renderReroutes(data, cardsDisplay);
    } catch(e) {
        cardsDisplay.innerHTML = '<div class="text-xs text-error p-3">Network error: ' + e.message + '</div>';
    } finally {
        btn.disabled = false;
        btn.textContent = '🔀 Generate Alternative Routes & Suggestions';
    }
}

// ── Update runTicketAnalysis to set ticket ref header ──
const _origRunTicketAnalysis = typeof runTicketAnalysis === 'function' ? runTicketAnalysis : null;

"""
    html = html[:insert_pos] + sim_js + html[insert_pos:]
    print("Sim mode JS injected")

# 3. Also update the runTicketAnalysis and viewTicketResult functions
# to set ticket-id/title in the header when switching to results
# Find the runTicketAnalysis function and add ticket header update
old_run = "document.getElementById('ticket-board-panel')?.classList.add('hidden');"
new_run = """document.getElementById('ticket-board-panel')?.classList.add('hidden');
        // Set ticket ref header
        const tktData = _allTickets.find(t => t.ticket_id === ticketId);
        if (tktData) {
            document.getElementById('result-ticket-id').textContent = tktData.ticket_id;
            document.getElementById('result-ticket-title').textContent = tktData.title;
        }
        // Reset to Normal sim mode
        switchSimMode('normal', document.getElementById('simtab-normal'));"""
html = html.replace(old_run, new_run, 1)
print("Updated runTicketAnalysis with ticket header")

# Remove the old sim-panels from left panel if they exist
if 'id="sim-panels"' in html:
    # Remove the whole sim-panels block
    import re
    html = re.sub(r'<div id="sim-panels".*?</div>\s*</div>\s*</div>\s*', '', html, flags=re.DOTALL, count=1)
    print("Removed old sim-panels from left panel")

with open(path, 'w', encoding='utf-8') as f:
    f.write(html)
print("Done.")
