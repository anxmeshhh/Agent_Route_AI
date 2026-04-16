"""
Inject threat/reroute JS functions into the ticket script block in analysis.html.
Insert before the closing </script> of the TICKET SYSTEM block.
Also update the _renderTicketCard to add threat/reroute buttons on completed tickets.
"""
path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\analysis.html'
with open(path, encoding='utf-8') as f:
    html = f.read()

# New JS to inject
threat_js = r"""

// ── Simulation panel switching ─────────────────────────
function switchSimPanel(panel, btn) {
    document.querySelectorAll('.sim-panel').forEach(p => p.classList.add('hidden'));
    document.querySelectorAll('.sim-tab').forEach(b => b.classList.remove('active'));
    document.getElementById('sim-' + panel)?.classList.remove('hidden');
    if (btn) btn.classList.add('active');
}

// ── THREAT ICONS ──────────────────────────────────────
const THREAT_ICONS = {
    piracy:'🏴‍☠️', storm:'🌪', port_closure:'🚫', mechanical:'⚙️',
    geopolitical:'🚨', fire:'🔥', collision:'💥', strike:'✊',
    earthquake:'🌊', flood:'🌧'
};

let _currentThreat = null;
let _threatTicketId = null;

// ── INDUCE THREAT ────────────────────────────────────
async function induceThreat(ticketId, ev) {
    if (ev) { ev.stopPropagation(); ev.preventDefault(); }
    _threatTicketId = ticketId;

    // Show sim panels and switch to threat tab
    document.getElementById('sim-panels')?.classList.remove('hidden');
    switchSimPanel('threat', document.querySelector('.threat-tab'));

    const display = document.getElementById('threat-display');
    display.innerHTML = '<div class="flex items-center gap-2 justify-center py-4"><span class="pulse-dot"></span><span class="text-[10px] text-[#ff6e84]">Generating threat via Groq AI...</span></div>';

    try {
        const r = await fetch(`/api/tickets/${ticketId}/threat`, {
            method:'POST', credentials:'include'
        });
        const data = await r.json();
        if (!r.ok || !data.success) {
            display.innerHTML = '<div class="text-[10px] text-error">Failed: ' + (data.error||'Unknown error') + '</div>';
            return;
        }
        _currentThreat = data.threat;
        renderThreatCard(data.threat, display);
    } catch(e) {
        display.innerHTML = '<div class="text-[10px] text-error">Network error: ' + e.message + '</div>';
    }
}

function renderThreatCard(t, container) {
    const icon = THREAT_ICONS[t.threat_type || t.type] || '⚠️';
    const sev  = t.severity || 'MEDIUM';
    container.innerHTML = `
      <div class="threat-card-panel threat-${sev}">
        <div class="flex items-start gap-2 mb-2">
          <span class="text-xl">${icon}</span>
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-1">
              <span class="threat-badge2 tb-${sev}">● ${sev} — ${(t.threat_type||t.type||'').replace(/_/g,' ').toUpperCase()}</span>
              <span class="text-[9px] text-[#757480] font-mono">ID: ${t.threat_id||'—'}</span>
            </div>
            <div class="text-sm font-bold text-white">${_esc(t.title || 'Unknown Threat')}</div>
          </div>
        </div>
        <div class="text-[11px] text-[#c8dff5] mb-3" style="line-height:1.6">${_esc(t.description || '')}</div>
        <div class="grid grid-cols-3 gap-2 mb-3">
          <div class="rounded-lg p-2" style="background:rgba(0,0,0,0.3)">
            <div class="text-[8px] font-mono text-[#4a6585] uppercase">Location</div>
            <div class="text-[11px] font-bold text-white">${_esc(t.location||'—')}</div>
          </div>
          <div class="rounded-lg p-2" style="background:rgba(0,0,0,0.3)">
            <div class="text-[8px] font-mono text-[#4a6585] uppercase">Delay</div>
            <div class="text-[11px] font-bold text-white">${t.estimated_delay_days||'?'} days</div>
          </div>
          <div class="rounded-lg p-2" style="background:rgba(0,0,0,0.3)">
            <div class="text-[8px] font-mono text-[#4a6585] uppercase">Radius</div>
            <div class="text-[11px] font-bold text-white">${t.affected_radius_km||'?'} km</div>
          </div>
        </div>
        <div class="rounded-lg p-2 mb-2 flex gap-2 items-start" style="background:rgba(0,212,255,0.07);border:1px solid rgba(0,212,255,0.2)">
          <span class="text-sm">💡</span>
          <div class="text-[10px] text-[#c8dff5]">${_esc(t.recommended_action||'')}</div>
        </div>
        <button class="reroute-btn-sm" onclick="getReroutes('${_threatTicketId}',event)">🔀 Generate Reroutes & Suggestions</button>
      </div>`;
}

// ── GET REROUTES ──────────────────────────────────────
async function getReroutes(ticketId, ev) {
    if (ev) { ev.stopPropagation(); ev.preventDefault(); }

    // Switch to suggestions tab
    switchSimPanel('suggest', document.querySelector('.suggest-tab'));
    const display = document.getElementById('reroute-display');
    display.innerHTML = '<div class="flex items-center gap-2 justify-center py-4"><span class="pulse-dot"></span><span class="text-[10px] text-[#93c5fd]">Generating alternative routes via Groq AI...</span></div>';

    try {
        const r = await fetch(`/api/tickets/${ticketId}/reroute`, {
            method:'POST', credentials:'include',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({threat: _currentThreat})
        });
        const data = await r.json();
        if (!r.ok || !data.success) {
            display.innerHTML = '<div class="text-[10px] text-error">Failed: ' + (data.error||'Unknown error') + '</div>';
            return;
        }
        renderReroutes(data, display);
    } catch(e) {
        display.innerHTML = '<div class="text-[10px] text-error">Network error: ' + e.message + '</div>';
    }
}

function renderReroutes(data, container) {
    const routes = data.routes || [];
    const weather = data.weather;
    const rec = data.final_recommendation;

    let wxHtml = '';
    if (weather) {
        const outlookCls = {'CLEAR':'text-[#4ade80]','MODERATE':'text-[#fde68a]','ROUGH':'text-[#fca5a5]','SEVERE':'text-[#ff6e84]'};
        wxHtml = `<div class="rounded-lg p-2 mb-3 flex items-center gap-2" style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06)">
            <span class="text-sm">🌤</span>
            <span class="text-[9px] font-mono text-[#4a6585] uppercase">Weather</span>
            <span class="text-[10px] ${outlookCls[weather.overall_outlook]||''} font-bold">${weather.overall_outlook||'—'}</span>
            <span class="text-[10px] text-[#abaab7] flex-1">${_esc(weather.summary||'')}</span>
        </div>`;
    }

    let recHtml = '';
    if (rec) {
        recHtml = `<div class="rounded-lg p-3 mb-3" style="background:rgba(74,222,128,0.06);border:1px solid rgba(74,222,128,0.2)">
            <div class="flex items-center gap-2 mb-1">
                <span class="text-sm">🏆</span>
                <span class="text-[10px] font-bold text-[#4ade80] uppercase">Best Route: ${_esc(rec.label||rec.route_id)}</span>
                <span class="mode-badge mode-${rec.mode||'SEA'}">${rec.mode||''}</span>
            </div>
            <div class="text-[10px] text-[#c8dff5]">${_esc(rec.reason||'')}</div>
        </div>`;
    }

    let routeCards = routes.map(r => {
        const modeEmoji = {AIR:'✈️',SEA:'🚢',MULTIMODAL:'🔄'}[r.mode]||'📦';
        const costDir = (r.cost_change_pct||0) > 0 ? 'up' : 'down';
        const isRec = r.recommended;
        const riskCls = {LOW:'text-[#4ade80]',MEDIUM:'text-[#fde68a]',HIGH:'text-[#ff6e84]'}[r.risk_level]||'';
        const waypoints = (r.waypoints||[]).map(w => `<span class="text-[9px] px-1.5 py-0.5 rounded" style="background:rgba(255,255,255,0.05)">${_esc(w)}</span>`).join('<span class="text-[8px] text-[#4a6585]">→</span>');

        return `<div class="reroute-card ${isRec?'rec':''}">
            <div class="flex items-start justify-between gap-2 mb-2">
                <div class="flex items-center gap-2">
                    <span class="text-sm">${modeEmoji}</span>
                    <span class="text-[9px] font-mono text-[#4a6585]">${r.route_id}</span>
                    <span class="mode-badge mode-${r.mode||'SEA'}">${r.mode||''}</span>
                    ${isRec?'<span class="rec-badge">★ RECOMMENDED</span>':''}
                </div>
                <span class="${riskCls} text-[9px] font-bold">${r.risk_level} (${r.risk_score}/100)</span>
            </div>
            <div class="text-xs font-bold text-white mb-1">${_esc(r.label||'')}</div>
            <div class="flex flex-wrap gap-1 items-center mb-2">${waypoints}</div>
            <div class="grid grid-cols-3 gap-2 mb-2">
                <div class="rounded p-1.5" style="background:rgba(0,0,0,0.2)">
                    <div class="text-[7px] font-mono text-[#4a6585] uppercase">Transit</div>
                    <div class="text-[11px] font-bold text-white">${r.transit_days}d <span class="text-[9px] text-[#4a6585]">/ orig ${r.original_transit_days||'?'}d</span></div>
                </div>
                <div class="rounded p-1.5" style="background:rgba(0,0,0,0.2)">
                    <div class="text-[7px] font-mono text-[#4a6585] uppercase">Cost</div>
                    <div class="text-[11px] font-bold text-white">$${(r.cost_usd||0).toLocaleString()} <span class="text-[9px] ${costDir==='up'?'text-[#fca5a5]':'text-[#4ade80]'}">${costDir==='up'?'+':''}${(r.cost_change_pct||0).toFixed(0)}%</span></div>
                </div>
                <div class="rounded p-1.5" style="background:rgba(0,0,0,0.2)">
                    <div class="text-[7px] font-mono text-[#4a6585] uppercase">Risk</div>
                    <div class="text-[11px] font-bold ${riskCls}">${r.risk_score}/100</div>
                </div>
            </div>
            <div class="text-[9px] text-[#abaab7] italic">${_esc(r.risk_reason||'')}</div>
        </div>`;
    }).join('');

    container.innerHTML = wxHtml + recHtml + routeCards;
}
"""

# Now update _renderTicketCard to add threat/reroute buttons on completed tickets
# Find the current render function and update the button section
old_done_line = """${done   ? \`<button class="btn-run-analysis" style="background:rgba(74,222,128,.12);color:#4ade80;border-color:rgba(74,222,128,.3)" onclick="viewTicketResult('\${t.ticket_id}',event)">📊 View</button>\` : ''}"""

new_done_line = """${done   ? \`<button class="btn-run-analysis" style="background:rgba(74,222,128,.12);color:#4ade80;border-color:rgba(74,222,128,.3)" onclick="viewTicketResult('\${t.ticket_id}',event)">📊 View</button>
              <button class="threat-btn-sm" onclick="induceThreat('\${t.ticket_id}',event)">⚡ Threat</button>\` : ''}"""

if old_done_line in html:
    html = html.replace(old_done_line, new_done_line, 1)
    print("Added threat/reroute buttons to completed cards")
else:
    print("WARNING: Could not find done button line for patching")

# Find the last ticket JS </script> and insert before it
# The ticket JS ends with the _timeAgo function followed by </script>
import re
# Find the TICKET SYSTEM script block's closing
match = re.search(r'(function _timeAgo\(dtStr\).*?}\s*\n)\s*</script>', html, re.DOTALL)
if match:
    insertion_point = match.end() - len('</script>')
    html = html[:insertion_point] + threat_js + '\n' + html[insertion_point:]
    print("Threat JS functions injected")
else:
    # Fallback: insert before last </body>
    html = html.replace('</body>', threat_js + '\n</script>\n</body>', 1)
    print("Threat JS injected via fallback")

with open(path, 'w', encoding='utf-8') as f:
    f.write(html)
print("Done.")
