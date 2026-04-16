"""Patch index.html: replace loadHistory call with loadTickets and inject new JS."""
path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\index.html'
with open(path, encoding='utf-8') as f:
    content = f.read()

# 1. Replace loadHistory() call inside loadCurrentUser to use loadTickets()
content = content.replace('        loadHistory();\n', '        loadTickets();\n')
print("1. loadHistory() -> loadTickets() in DOMContentLoaded:", 'loadTickets' in content)

# 2. Replace the entire loadHistory() function block with the new loadTickets + filter functions
old_fn = '''async function loadHistory() {
    try {
        const r = await fetch('/api/history', { credentials: 'include' });
        if (!r.ok) return;
        const items = await r.json();
        document.getElementById('stat-total').textContent = items.length;
        const container = document.getElementById('recent-analyses');
        if (!items.length) return;
        container.innerHTML = items.slice(0, 8).map(it => {
            const ts = it.created_at ? new Date(it.created_at).toLocaleString() : '—';
            const statusBg = it.status==='failed' ? 'bg-error-container/20 text-error border-error/20' : 'bg-secondary-container/20 text-secondary border-secondary/20';
            return `<div class="glass-panel p-4 rounded-xl border border-white/5 hover:bg-surface-bright/30 transition-all cursor-pointer group" onclick="window.location.href='/analysis'">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3 flex-1 min-w-0">
                        <div class="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center flex-shrink-0">
                            <span class="material-symbols-outlined text-secondary">alt_route</span>
                        </div>
                        <div class="min-w-0">
                            <div class="text-sm font-bold text-white truncate group-hover:text-secondary transition-colors">${it.query || 'Analysis'}</div>
                            <div class="text-[10px] text-outline font-mono">${ts} • #${(it.session_id||'').substring(0,8)}</div>
                        </div>
                    </div>
                    <span class="px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider border ${statusBg} flex-shrink-0 ml-3">${it.status||'completed'}</span>
                </div>
            </div>`;
        }).join('');
    } catch(e) { console.error('History load failed:', e); }
}'''

new_fn = '''let _dashTickets = [];
let _dashFilter  = 'all';

async function loadTickets() {
    try {
        const r = await fetch('/api/tickets', { credentials: 'include' });
        if (!r.ok) { await loadHistory(); return; }
        const data = await r.json();
        _dashTickets = data.tickets || [];
        document.getElementById('stat-total').textContent = _dashTickets.length;
        _renderDashTickets();
    } catch(e) { console.error('Tickets load failed:', e); await loadHistory(); }
}

function _renderDashTickets() {
    const container = document.getElementById('recent-analyses');
    const filtered = _dashFilter === 'all' ? _dashTickets : _dashTickets.filter(t => t.status === _dashFilter);
    if (!filtered.length) {
        const label = _dashFilter === 'all' ? '' : _dashFilter + ' ';
        container.innerHTML = `<div class="glass-panel p-6 rounded-xl border border-white/5 text-center text-on-surface-variant">
            <span class="material-symbols-outlined text-4xl text-outline mb-2 block">confirmation_number</span>
            <p class="text-sm">No ${label}tickets yet. <a href="/analysis" class="text-secondary font-bold">Launch your first analysis &rarr;</a></p>
        </div>`;
        return;
    }
    const modeIcon = { road:'🚗', sea:'🚢', air:'✈️' };
    const statusCls = {
        open:        'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
        in_progress: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
        completed:   'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
        failed:      'bg-red-500/10 text-red-400 border-red-500/20',
        closed:      'bg-slate-500/10 text-slate-400 border-slate-500/20',
    };
    const priorityDot = { low:'#4ade80', medium:'#fde68a', high:'#f97316', critical:'#ef4444' };
    container.innerHTML = filtered.slice(0, 10).map(t => {
        const hasThreat   = !!t.threat_json;
        const hasReroutes = !!t.reroute_json;
        const sc = statusCls[t.status] || statusCls.open;
        const pd = priorityDot[t.priority] || '#aaa';
        const url = `/analysis?uuid=${encodeURIComponent(t.shipment_uuid)}&ticket=${encodeURIComponent(t.ticket_id)}`;
        return `<div class="glass-panel p-4 rounded-xl border border-white/5 hover:bg-surface-bright/30 hover:border-secondary/20 hover:translate-y-[-1px] transition-all cursor-pointer group" onclick="window.location.href='${url}'">
            <div class="flex items-start justify-between gap-3">
                <div class="flex items-start gap-3 flex-1 min-w-0">
                    <div class="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center flex-shrink-0 text-lg">${modeIcon[t.transport_mode] || '📦'}</div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 mb-0.5">
                            <span class="text-[10px] font-mono font-bold text-primary">${t.ticket_id}</span>
                            <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" style="background:${pd}"></span>
                            <span class="text-[9px] text-outline uppercase tracking-wide">${t.priority || 'medium'}</span>
                        </div>
                        <div class="text-sm font-bold text-white truncate group-hover:text-secondary transition-colors">${t.title || t.shipment_uuid}</div>
                        <div class="text-[10px] text-outline mt-0.5">${t.origin || '?'} &rarr; ${t.destination || '?'} &middot; ${(t.transport_mode || '?').toUpperCase()} &middot; ${t.cargo_type || '?'}</div>
                        <div class="flex items-center gap-2 mt-1.5">
                            <span class="text-[9px] font-mono text-outline">${t.shipment_uuid ? t.shipment_uuid.substring(0,18) + '&hellip;' : '&mdash;'}</span>
                            ${hasThreat   ? '<span class="px-1.5 py-0.5 rounded text-[8px] font-bold bg-red-900/30 text-red-400 border border-red-500/20">⚡ Threat</span>' : ''}
                            ${hasReroutes ? '<span class="px-1.5 py-0.5 rounded text-[8px] font-bold bg-blue-900/30 text-blue-400 border border-blue-500/20">🔀 Rerouted</span>' : ''}
                        </div>
                    </div>
                </div>
                <div class="flex flex-col items-end gap-2 flex-shrink-0">
                    <span class="px-2 py-1 rounded-md text-[9px] font-bold uppercase tracking-wider border ${sc}">${t.status || 'open'}</span>
                    <span class="text-[9px] text-outline font-mono">${t.created_at ? new Date(t.created_at.replace(' ','T')).toLocaleDateString() : '&mdash;'}</span>
                </div>
            </div>
        </div>`;
    }).join('');
}

function dashFilterTickets(status, btn) {
    _dashFilter = status;
    document.querySelectorAll('#dash-ticket-filters button').forEach(b => {
        b.style.background = '';
        b.style.color = '';
        b.style.borderColor = '';
        b.setAttribute('data-active','');
    });
    btn.style.background = 'rgba(0,217,255,0.15)';
    btn.style.color = '#00d9ff';
    btn.style.borderColor = 'rgba(0,217,255,0.3)';
    _renderDashTickets();
}

async function loadHistory() {
    try {
        const r = await fetch('/api/history', { credentials: 'include' });
        if (!r.ok) return;
        const items = await r.json();
        document.getElementById('stat-total').textContent = items.length;
        const container = document.getElementById('recent-analyses');
        if (!items.length) return;
        container.innerHTML = items.slice(0, 8).map(it => {
            const ts = it.created_at ? new Date(it.created_at).toLocaleString() : '—';
            const statusBg = it.status==='failed' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20';
            return `<div class="glass-panel p-4 rounded-xl border border-white/5 hover:bg-surface-bright/30 transition-all cursor-pointer group" onclick="window.location.href='/analysis'">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3 flex-1 min-w-0">
                        <div class="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center flex-shrink-0">
                            <span class="material-symbols-outlined text-secondary">alt_route</span>
                        </div>
                        <div class="min-w-0">
                            <div class="text-sm font-bold text-white truncate group-hover:text-secondary transition-colors">${it.query || 'Analysis'}</div>
                            <div class="text-[10px] text-outline font-mono">${ts}</div>
                        </div>
                    </div>
                    <span class="px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider border ${statusBg} flex-shrink-0 ml-3">${it.status||'completed'}</span>
                </div>
            </div>`;
        }).join('');
    } catch(e) { console.error('History load failed:', e); }
}'''

if old_fn in content:
    content = content.replace(old_fn, new_fn)
    print("2. Replaced loadHistory with loadTickets+helpers: OK")
else:
    # Try to find a partial match
    idx = content.find('async function loadHistory()')
    print(f"2. loadHistory not found by full match. Index: {idx}")
    if idx > -1:
        # Insert new functions before loadHistory
        content = content[:idx] + new_fn + '\n\n' + content[idx:]
        print("   Inserted before existing loadHistory")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done.")
