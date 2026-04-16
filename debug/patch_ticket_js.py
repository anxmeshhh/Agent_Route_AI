"""Inject ticket system JavaScript into analysis.html, before the existing </body> close."""
import os
path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\analysis.html'
with open(path, 'r', encoding='utf-8') as f:
    html = f.read()

ticket_js = r"""
<script>
// ══════════════════════════════════════════════════════
//  TICKET SYSTEM — full JS
// ══════════════════════════════════════════════════════
let _ticketFilter  = 'all';
let _allTickets    = [];
let _activeTicket  = null;

// ── Render a single ticket card ───────────────────────
function _renderTicketCard(t) {
    const modeIcon = {road:'🚗',sea:'🚢',air:'✈'}[t.transport_mode]||'📦';
    const running  = t.status === 'in_progress';
    const done     = t.status === 'completed';
    const closed   = t.status === 'closed';
    const canRun   = !running && !closed;

    const since = t.created_at ? _timeAgo(t.created_at) : '';
    const weight = t.weight_kg  ? `${Number(t.weight_kg).toLocaleString()} kg` : '';
    const budget = t.budget_usd ? `$${Number(t.budget_usd).toLocaleString()}` : '';
    const eta    = t.eta_days   ? `${t.eta_days}d` : '';

    const meta = [modeIcon + ' ' + (t.transport_mode||'').toUpperCase(),
                  weight, budget, eta].filter(Boolean).join(' · ');

    const card = document.createElement('div');
    card.className = 'ticket-card' + (_activeTicket === t.ticket_id ? ' selected' : '');
    card.dataset.ticketId = t.ticket_id;
    card.innerHTML = `
      <div class="flex items-start justify-between gap-2">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <span class="tkt-id">${t.ticket_id}</span>
            <span class="tkt-status s-${t.status}">${running?'<span class="pulse-dot mr-1"></span>':''} ${t.status.replace('_',' ')}</span>
            <span class="tkt-priority p-${t.priority}">${t.priority}</span>
          </div>
          <div class="tkt-title">${_esc(t.title)}</div>
          <div class="tkt-meta">${_esc(meta)}<span class="ml-auto opacity-60">${since}</span></div>
        </div>
        <div class="flex flex-col gap-1 flex-shrink-0">
          ${canRun ? `<button class="btn-run-analysis" onclick="runTicketAnalysis('${t.ticket_id}',event)">▶ Run</button>` : ''}
          ${done   ? `<button class="btn-run-analysis" onclick="viewTicketResult('${t.ticket_id}',event)" style="background:rgba(74,222,128,.12);color:#4ade80;border-color:rgba(74,222,128,.3)">📊 View</button>` : ''}
          ${!closed ? `<button class="btn-close-ticket" onclick="closeTicket('${t.ticket_id}',event)">✕</button>` : ''}
        </div>
      </div>`;
    return card;
}

// ── Load + render all tickets for current shipment UUID ─
async function loadTickets() {
    const uuid = (document.getElementById('shipment-uuid')||{}).value||'';
    const boardUUID = document.getElementById('board-shipment-uuid');
    if (boardUUID) boardUUID.textContent = uuid || '—';
    if (!uuid) return;

    const statusQ = _ticketFilter !== 'all' ? '&status='+_ticketFilter : '';
    try {
        const r = await fetch(`/api/tickets?shipment_uuid=${encodeURIComponent(uuid)}${statusQ}`,
                              {credentials:'include'});
        if (!r.ok) return;
        const data = await r.json();
        _allTickets = data.tickets || [];
        _renderTicketList();
    } catch(e) { console.warn('[tickets] load error:', e); }
}

function _renderTicketList() {
    const list = document.getElementById('ticket-list');
    const empty = document.getElementById('ticket-empty-state');
    if (!list) return;
    // clear old cards
    list.querySelectorAll('.ticket-card').forEach(n => n.remove());

    const filtered = _ticketFilter === 'all'
        ? _allTickets
        : _allTickets.filter(t => t.status === _ticketFilter);

    const openCount = _allTickets.filter(t => t.status === 'open').length;
    const badge = document.getElementById('open-ticket-count');
    if (badge) badge.textContent = openCount + ' open';

    if (filtered.length === 0) {
        if (empty) empty.classList.remove('hidden');
        return;
    }
    if (empty) empty.classList.add('hidden');
    filtered.forEach(t => list.appendChild(_renderTicketCard(t)));
}

function filterTickets(status, btn) {
    _ticketFilter = status;
    document.querySelectorAll('.ticket-filter-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    _renderTicketList();
}

// ── Create ticket (form submit) ────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    genUUID();

    const form = document.getElementById('analysis-form');
    if (!form) return;
    const newForm = form.cloneNode(true);
    form.parentNode.replaceChild(newForm, form);

    newForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const errBox = document.getElementById('form-error');
        errBox.classList.add('hidden');

        const origin = (document.getElementById('inp-origin')?.value||'').trim();
        const dest   = (document.getElementById('inp-dest')?.value||'').trim();
        if (!origin || !dest) {
            errBox.textContent = 'Origin and Destination are required';
            errBox.classList.remove('hidden');
            return;
        }

        const uuid = document.getElementById('shipment-uuid')?.value || '';
        const cargo= document.getElementById('inp-cargo')?.value || 'general';

        const payload = {
            shipment_uuid:  uuid,
            origin,
            destination:    dest,
            cargo_type:     cargo,
            transport_mode: _currentRouteType || 'road',
            weight_kg:      parseFloat(document.getElementById('inp-weight')?.value)||null,
            budget_usd:     parseFloat(document.getElementById('inp-budget')?.value)||null,
            eta_days:       parseInt(document.getElementById('inp-eta')?.value)||null,
            priority:       'medium',
        };

        const btn = document.getElementById('analyze-btn');
        const txt = document.getElementById('btn-text');
        const spin= document.getElementById('btn-spinner');
        if (txt) txt.textContent = 'Creating…';
        if (spin) spin.classList.remove('hidden');
        if (btn) btn.disabled = true;

        try {
            const r = await fetch('/api/tickets', {
                method:'POST', headers:{'Content-Type':'application/json'},
                credentials:'include', body: JSON.stringify(payload),
            });
            const data = await r.json();
            if (!r.ok) {
                errBox.textContent = data.error || 'Failed to create ticket';
                errBox.classList.remove('hidden');
                return;
            }
            // Refresh ticket board
            await loadTickets();
            // Show success flash briefly
            if (txt) txt.textContent = '✓ Ticket Created!';
            setTimeout(() => { if(txt) txt.textContent = '🎫 Create Ticket'; }, 1500);
        } catch(err) {
            errBox.textContent = 'Network error: ' + err.message;
            errBox.classList.remove('hidden');
        } finally {
            if (spin) spin.classList.add('hidden');
            if (btn) btn.disabled = false;
            if (txt && txt.textContent === 'Creating…') txt.textContent = '🎫 Create Ticket';
        }
    });

    // Re-load tickets when UUID changes
    const uuidEl = document.getElementById('shipment-uuid');
    if (uuidEl) uuidEl.addEventListener('change', loadTickets);

    // Initial load if UUID already set
    setTimeout(loadTickets, 600);
});

// Update board UUID display when UUID input changes
function genUUID() {
    const seg = () => Math.random().toString(36).substr(2,8).toUpperCase();
    const val = 'SHP-' + seg();
    const el_ = document.getElementById('shipment-uuid');
    if (el_) el_.value = val;
    const bdEl = document.getElementById('board-shipment-uuid');
    if (bdEl) bdEl.textContent = val;
}

// ── Run analysis for a ticket ──────────────────────────
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

        // Switch right panel to results view
        document.getElementById('ticket-board-panel')?.classList.add('hidden');
        document.getElementById('results-state')?.classList.remove('hidden');
        document.getElementById('results-state')?.classList.add('flex');

        // Start SSE stream
        if (typeof window.startSSEStream === 'function') {
            window.startSSEStream(data.session_id, data.stream_url);
        } else {
            const es = new EventSource(data.stream_url);
            es.onmessage = ev2 => {
                try { window._handleSSEData && window._handleSSEData(JSON.parse(ev2.data)); } catch(_){}
            };
            es.addEventListener('done', () => {
                es.close();
                setTimeout(() => {
                    document.getElementById('ticket-board-panel')?.classList.remove('hidden');
                    loadTickets();
                }, 3000);
            });
        }
    } catch(e) { console.error('[ticket] analyze error:', e); }
}

// ── View cached result ─────────────────────────────────
async function viewTicketResult(ticketId, ev) {
    if (ev) { ev.stopPropagation(); ev.preventDefault(); }
    try {
        const r = await fetch(`/api/tickets/${ticketId}`, {credentials:'include'});
        const data = await r.json();
        if (!r.ok || !data.ticket?.result) return;
        document.getElementById('ticket-board-panel')?.classList.add('hidden');
        document.getElementById('results-state')?.classList.remove('hidden');
        document.getElementById('results-state')?.classList.add('flex');
        if (typeof window._handleSSEData === 'function') {
            window._handleSSEData(data.ticket.result);
        }
    } catch(e) { console.error('[ticket] view error:', e); }
}

// ── Close/archive ticket ───────────────────────────────
async function closeTicket(ticketId, ev) {
    if (ev) { ev.stopPropagation(); ev.preventDefault(); }
    await fetch(`/api/tickets/${ticketId}/status`, {
        method:'PATCH', headers:{'Content-Type':'application/json'},
        credentials:'include', body: JSON.stringify({status:'closed'})
    });
    loadTickets();
}

// ── Utility ───────────────────────────────────────────
function _esc(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function _timeAgo(dtStr) {
    const d = new Date(dtStr.replace(' ','T')+'Z');
    const s = Math.floor((Date.now()-d)/1000);
    if (s<60)  return s+'s ago';
    if (s<3600) return Math.floor(s/60)+'m ago';
    if (s<86400) return Math.floor(s/3600)+'h ago';
    return Math.floor(s/86400)+'d ago';
}

// expose for btn-land/sea/air
let _currentRouteType = 'road';
const _origSetRouteType = typeof setRouteType === 'function' ? setRouteType : null;
function setRouteType(t) {
    _currentRouteType = t;
    if (_origSetRouteType) _origSetRouteType(t);
    document.querySelectorAll('.route-type-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-'+t)?.classList.add('active');
}
</script>
"""

# Insert before </body>
if '</body></html>' in html:
    html = html.replace('</body></html>', ticket_js + '\n</body></html>', 1)
    print("Ticket JS injected.")
else:
    print("WARNING: closing tag not found")

with open(path, 'w', encoding='utf-8') as f:
    f.write(html)
print("Done.")
