"""
Replace the entire ticket JS block in analysis.html (lines 749-1015, the <script> block)
with a clean version that:
1. Has no recursive setRouteType
2. Calls main.js openSSE directly for streaming
3. Wires the results panel toggle properly
"""
path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\analysis.html'
with open(path, encoding='utf-8') as f:
    html = f.read()

# Find and replace the whole ticket <script>...</script> block
import re
# Match from the opener <script> that contains "TICKET SYSTEM" to its closing </script>
pattern = r'<script>\s*// ═+\s*//\s*TICKET SYSTEM.*?</script>'
match = re.search(pattern, html, re.DOTALL)
if not match:
    print("ERROR: Ticket JS block not found via regex")
    # Try line-based
    lines = html.split('\n')
    start = end = None
    for i, l in enumerate(lines):
        if 'TICKET SYSTEM' in l and start is None:
            # find the <script> tag above
            for j in range(i, max(0, i-5), -1):
                if '<script>' in lines[j]:
                    start = j; break
        if start is not None and i > start and '</script>' in l:
            end = i; break
    if start is not None and end is not None:
        print(f"Found via line scan: {start+1}-{end+1}")
        old_block = '\n'.join(lines[start:end+1])
    else:
        print("FATAL: Cannot locate ticket JS block")
        exit(1)
else:
    old_block = match.group(0)
    print(f"Found via regex at pos {match.start()}-{match.end()}")

new_block = r"""<script>
// ══════════════════════════════════════════════════════
//  TICKET SYSTEM — v2 (no recursive setRouteType)
// ══════════════════════════════════════════════════════
let _ticketFilter  = 'all';
let _allTickets    = [];
let _activeTicket  = null;
let _currentRouteType = 'road';

// ── Route mode selector ───────────────────────────────
function setRouteType(t) {
    _currentRouteType = t;
    document.querySelectorAll('.route-type-btn').forEach(b => b.classList.remove('active'));
    const map = {road:'btn-land', sea:'btn-sea', air:'btn-air'};
    document.getElementById(map[t] || 'btn-land')?.classList.add('active');
}

// ── UUID Generator ────────────────────────────────────
function genUUID() {
    const seg = () => Math.random().toString(36).substr(2,8).toUpperCase();
    const val = 'SHP-' + seg();
    const el_ = document.getElementById('shipment-uuid');
    if (el_) el_.value = val;
    const bdEl = document.getElementById('board-shipment-uuid');
    if (bdEl) bdEl.textContent = val;
}

// ── Quick fill examples ───────────────────────────────
function fillExample(origin, dest, cargo, eta, budget, weight) {
    document.getElementById('inp-origin').value  = origin;
    document.getElementById('inp-dest').value    = dest;
    document.getElementById('inp-cargo').value   = cargo;
    document.getElementById('inp-eta').value     = eta;
    document.getElementById('inp-budget').value  = budget;
    document.getElementById('inp-weight').value  = weight;
    if (!document.getElementById('shipment-uuid').value) genUUID();
}

// ── Render a single ticket card ───────────────────────
function _renderTicketCard(t) {
    const modeIcon = {road:'🚗',sea:'🚢',air:'✈'}[t.transport_mode] || '📦';
    const running  = t.status === 'in_progress';
    const done     = t.status === 'completed';
    const closed   = t.status === 'closed';
    const canRun   = !running && !closed;

    const weight = t.weight_kg  ? `${Number(t.weight_kg).toLocaleString()} kg` : '';
    const budget = t.budget_usd ? `$${Number(t.budget_usd).toLocaleString()}` : '';
    const eta    = t.eta_days   ? `${t.eta_days}d` : '';
    const meta   = [modeIcon + ' ' + (t.transport_mode||'').toUpperCase(), weight, budget, eta].filter(Boolean).join(' · ');
    const since  = t.created_at ? _timeAgo(t.created_at) : '';

    const card = document.createElement('div');
    card.className = 'ticket-card' + (_activeTicket === t.ticket_id ? ' selected' : '');
    card.dataset.ticketId = t.ticket_id;
    card.innerHTML = `
      <div class="flex items-start justify-between gap-2">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <span class="tkt-id">${t.ticket_id}</span>
            <span class="tkt-status s-${t.status}">${running ? '<span class="pulse-dot mr-1"></span>' : ''}${t.status.replace('_',' ')}</span>
            <span class="tkt-priority p-${t.priority}">${t.priority}</span>
          </div>
          <div class="tkt-title">${_esc(t.title)}</div>
          <div class="tkt-meta">${_esc(meta)}<span class="ml-auto opacity-60">${since}</span></div>
        </div>
        <div class="flex flex-col gap-1 flex-shrink-0 mt-1">
          ${canRun ? `<button class="btn-run-analysis" onclick="runTicketAnalysis('${t.ticket_id}',event)">▶ Run</button>` : ''}
          ${done   ? `<button class="btn-run-analysis" style="background:rgba(74,222,128,.12);color:#4ade80;border-color:rgba(74,222,128,.3)" onclick="viewTicketResult('${t.ticket_id}',event)">📊 View</button>` : ''}
          ${!closed ? `<button class="btn-close-ticket" onclick="closeTicket('${t.ticket_id}',event)">✕</button>` : ''}
        </div>
      </div>`;
    return card;
}

// ── Load and render tickets ────────────────────────────
async function loadTickets() {
    const uuid = (document.getElementById('shipment-uuid') || {}).value || '';
    const bdEl = document.getElementById('board-shipment-uuid');
    if (bdEl) bdEl.textContent = uuid || '—';
    if (!uuid) return;

    const q = _ticketFilter !== 'all' ? '&status=' + _ticketFilter : '';
    try {
        const r = await fetch(`/api/tickets?shipment_uuid=${encodeURIComponent(uuid)}${q}`, {credentials:'include'});
        if (!r.ok) return;
        const data = await r.json();
        _allTickets = data.tickets || [];
        _renderTicketList();
    } catch(e) { console.warn('[tickets] load error:', e); }
}

function _renderTicketList() {
    const list  = document.getElementById('ticket-list');
    const empty = document.getElementById('ticket-empty-state');
    if (!list) return;
    list.querySelectorAll('.ticket-card').forEach(n => n.remove());

    const filtered = _ticketFilter === 'all' ? _allTickets : _allTickets.filter(t => t.status === _ticketFilter);
    const openCnt  = _allTickets.filter(t => t.status === 'open' || t.status === 'in_progress').length;
    const badge    = document.getElementById('open-ticket-count');
    if (badge) badge.textContent = openCnt + ' open';

    if (filtered.length === 0) { if (empty) empty.classList.remove('hidden'); return; }
    if (empty) empty.classList.add('hidden');
    filtered.forEach(t => list.appendChild(_renderTicketCard(t)));
}

function filterTickets(status, btn) {
    _ticketFilter = status;
    document.querySelectorAll('.ticket-filter-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    _renderTicketList();
}

// ── CREATE TICKET (form submit) ────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    genUUID();

    // Wire example chips
    const ex1 = document.getElementById('ex1');
    const ex2 = document.getElementById('ex2');
    const ex3 = document.getElementById('ex3');
    if (ex1) ex1.onclick = () => fillExample('Delhi','Kochi','pharmaceuticals',3,25000,500);
    if (ex2) ex2.onclick = () => fillExample('Mumbai','Bangalore','electronics',2,15000,200);
    if (ex3) ex3.onclick = () => fillExample('Shanghai','Rotterdam','electronics',28,85000,18000);

    // Re-load tickets when UUID changes
    const uuidEl = document.getElementById('shipment-uuid');
    if (uuidEl) uuidEl.addEventListener('change', loadTickets);
    setTimeout(loadTickets, 600);

    // Form submit → create ticket
    const form = document.getElementById('analysis-form');
    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        const errBox = document.getElementById('form-error');
        if (errBox) errBox.classList.add('hidden');

        const origin = (document.getElementById('inp-origin')?.value || '').trim();
        const dest   = (document.getElementById('inp-dest')?.value   || '').trim();
        if (!origin || !dest) {
            if (errBox) { errBox.textContent = 'Origin and Destination are required'; errBox.classList.remove('hidden'); }
            return;
        }

        const uuid = document.getElementById('shipment-uuid')?.value || '';
        const payload = {
            shipment_uuid:  uuid,
            origin,
            destination:    dest,
            cargo_type:     document.getElementById('inp-cargo')?.value || 'general',
            transport_mode: _currentRouteType || 'road',
            weight_kg:      parseFloat(document.getElementById('inp-weight')?.value) || null,
            budget_usd:     parseFloat(document.getElementById('inp-budget')?.value) || null,
            eta_days:       parseInt(document.getElementById('inp-eta')?.value)       || null,
            priority:       'medium',
        };

        const btn  = document.getElementById('analyze-btn');
        const txt  = document.getElementById('btn-text');
        const spin = document.getElementById('btn-spinner');
        if (txt)  txt.textContent = 'Creating…';
        if (spin) spin.classList.remove('hidden');
        if (btn)  btn.disabled = true;

        try {
            const r    = await fetch('/api/tickets', {
                method:'POST', headers:{'Content-Type':'application/json'},
                credentials:'include', body: JSON.stringify(payload)
            });
            const data = await r.json();
            if (!r.ok) {
                if (errBox) { errBox.textContent = data.error || 'Failed to create ticket'; errBox.classList.remove('hidden'); }
                return;
            }
            await loadTickets();
            if (txt) txt.textContent = '✓ Ticket Created!';
            setTimeout(() => { if (txt) txt.textContent = '🎫 Create Ticket'; }, 1600);
        } catch(err) {
            if (errBox) { errBox.textContent = 'Network error: ' + err.message; errBox.classList.remove('hidden'); }
        } finally {
            if (spin) spin.classList.add('hidden');
            if (btn)  btn.disabled = false;
            if (txt && txt.textContent === 'Creating…') txt.textContent = '🎫 Create Ticket';
        }
    });
});

// ── RUN ANALYSIS for a ticket ──────────────────────────
async function runTicketAnalysis(ticketId, ev) {
    if (ev) { ev.stopPropagation(); ev.preventDefault(); }
    _activeTicket = ticketId;
    _renderTicketList();

    try {
        const r = await fetch(`/api/tickets/${ticketId}/analyze`, {
            method:'POST', credentials:'include'
        });
        const data = await r.json();
        if (!r.ok) { alert(data.error || 'Failed to start analysis'); return; }

        // Switch to results view
        document.getElementById('ticket-board-panel')?.classList.add('hidden');
        const resState = document.getElementById('results-state');
        if (resState) { resState.classList.remove('hidden'); resState.style.display = 'flex'; }

        // Use main.js openSSE — pass null for btn/text/spinner since we manage our own UI
        if (typeof openSSE === 'function') {
            openSSE(data.session_id, null, null, null);
        } else {
            // Manual fallback
            const es = new EventSource(data.stream_url);
            es.addEventListener('agent_log', ev2 => {
                try { handleLog && handleLog(JSON.parse(ev2.data)?.data || JSON.parse(ev2.data)); } catch(_){}
            });
            es.addEventListener('result', ev2 => {
                try {
                    const w = JSON.parse(ev2.data);
                    const result = w.data || w;
                    es.close();
                    if (typeof onComplete === 'function') onComplete(result, null, null, null);
                } catch(_){}
            });
            es.addEventListener('error', ev2 => { es.close(); });
            es.addEventListener('done',  () => { es.close(); });
        }

        // After 3s, refresh ticket board in background to show updated status
        setTimeout(() => {
            loadTickets();
            // Show Back button
            const backBtn = document.getElementById('back-to-board-btn');
            if (backBtn) backBtn.classList.remove('hidden');
        }, 2000);

    } catch(e) { console.error('[ticket] analyze error:', e); }
}

// ── VIEW CACHED RESULT ────────────────────────────────
async function viewTicketResult(ticketId, ev) {
    if (ev) { ev.stopPropagation(); ev.preventDefault(); }
    try {
        const r    = await fetch(`/api/tickets/${ticketId}`, {credentials:'include'});
        const data = await r.json();
        if (!r.ok || !data.ticket?.result) { alert('No results cached yet for this ticket.'); return; }
        document.getElementById('ticket-board-panel')?.classList.add('hidden');
        const resState = document.getElementById('results-state');
        if (resState) { resState.classList.remove('hidden'); resState.style.display = 'flex'; }
        if (typeof onComplete === 'function') onComplete(data.ticket.result, null, null, null);
        const backBtn = document.getElementById('back-to-board-btn');
        if (backBtn) backBtn.classList.remove('hidden');
    } catch(e) { console.error('[ticket] view error:', e); }
}

// ── CLOSE TICKET ──────────────────────────────────────
async function closeTicket(ticketId, ev) {
    if (ev) { ev.stopPropagation(); ev.preventDefault(); }
    if (!confirm('Archive this ticket?')) return;
    await fetch(`/api/tickets/${ticketId}/status`, {
        method:'PATCH', headers:{'Content-Type':'application/json'},
        credentials:'include', body: JSON.stringify({status:'closed'})
    });
    loadTickets();
}

// ── Back to board button handler ──────────────────────
function backToBoard() {
    document.getElementById('ticket-board-panel')?.classList.remove('hidden');
    document.getElementById('results-state')?.classList.add('hidden');
    document.getElementById('back-to-board-btn')?.classList.add('hidden');
    _activeTicket = null;
    loadTickets();
}

// ── Expose for main.js onComplete ─────────────────────
window._handleSSEData = function(result) {
    if (typeof onComplete === 'function') onComplete(result, null, null, null);
};

// ── Utils ──────────────────────────────────────────────
function _esc(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function _timeAgo(dtStr) {
    try {
        const d = new Date(dtStr.replace(' ','T'));
        const s = Math.floor((Date.now() - d) / 1000);
        if (s < 60) return s + 's ago';
        if (s < 3600) return Math.floor(s/60) + 'm ago';
        if (s < 86400) return Math.floor(s/3600) + 'h ago';
        return Math.floor(s/86400) + 'd ago';
    } catch(_) { return ''; }
}
</script>"""

html = html.replace(old_block, new_block, 1)
with open(path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"Replaced {len(old_block)} chars with {len(new_block)} chars")
print("Done.")
