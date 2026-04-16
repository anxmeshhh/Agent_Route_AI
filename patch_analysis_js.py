"""Inject new form JS into analysis.html"""
path = r'c:\Users\Animesh\Desktop\Test agentic ai\shipment_risk_agent\app\templates\analysis.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

new_js = r"""
<script>
// ── UUID Generator ─────────────────────────────────────
function genUUID() {
    const seg = () => Math.random().toString(36).substr(2,8).toUpperCase();
    document.getElementById('shipment-uuid').value = 'SHP-' + seg();
}

// ── Fill example ────────────────────────────────────────
function fillExample(origin, dest, cargo, eta, budget, weight) {
    document.getElementById('inp-origin').value  = origin;
    document.getElementById('inp-dest').value    = dest;
    document.getElementById('inp-cargo').value   = cargo;
    document.getElementById('inp-eta').value     = eta;
    document.getElementById('inp-budget').value  = budget;
    document.getElementById('inp-weight').value  = weight;
    if (!document.getElementById('shipment-uuid').value) genUUID();
}

// ── Wire example chips ──────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    // Auto-generate UUID on load
    genUUID();

    // Load user info for role label
    fetch('/api/auth/me', {credentials:'include'})
        .then(r => r.ok ? r.json() : null)
        .then(u => {
            if (!u) return;
            const lbl = document.getElementById('user-role-label');
            if (lbl) {
                const roleIcon = u.role === 'admin' ? '🛡️' : '👤';
                lbl.textContent = roleIcon + ' ' + (u.display_name||u.role) + ' · ' + (u.org_name||'');
            }
        }).catch(() => {});

    const ex1 = document.getElementById('ex1');
    const ex2 = document.getElementById('ex2');
    const ex3 = document.getElementById('ex3');
    if (ex1) ex1.addEventListener('click', () => fillExample('Delhi','Kochi','pharmaceuticals',3,25000,500));
    if (ex2) ex2.addEventListener('click', () => fillExample('Mumbai','Bangalore','electronics',2,15000,200));
    if (ex3) ex3.addEventListener('click', () => fillExample('Shanghai','Rotterdam','electronics',28,85000,18000));
});

// ── Override form submission ─────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('analysis-form');
    if (!form) return;

    // Remove any existing listeners by cloning
    const newForm = form.cloneNode(true);
    form.parentNode.replaceChild(newForm, form);

    newForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const errBox = document.getElementById('form-error');
        errBox.classList.add('hidden');

        const origin = (document.getElementById('inp-origin')?.value || '').trim();
        const dest   = (document.getElementById('inp-dest')?.value || '').trim();

        if (!origin || !dest) {
            errBox.textContent = 'Origin and Destination are required';
            errBox.classList.remove('hidden');
            return;
        }

        const payload = {
            origin:        origin,
            destination:   dest,
            cargo_type:    document.getElementById('inp-cargo')?.value || 'general',
            weight_kg:     parseFloat(document.getElementById('inp-weight')?.value) || null,
            budget_usd:    parseFloat(document.getElementById('inp-budget')?.value) || null,
            eta_days:      parseInt(document.getElementById('inp-eta')?.value)    || null,
            shipment_uuid: document.getElementById('shipment-uuid')?.value || '',
        };

        const btn    = document.getElementById('analyze-btn');
        const btnTxt = document.getElementById('btn-text');
        const spin   = document.getElementById('btn-spinner');
        btnTxt.textContent = 'Launching agents…';
        spin?.classList.remove('hidden');
        if (btn) btn.disabled = true;

        try {
            const res  = await fetch('/api/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify(payload),
            });
            const data = await res.json();

            if (!res.ok) {
                errBox.textContent = data.error || 'Analysis failed';
                errBox.classList.remove('hidden');
                return;
            }

            // Show UUID in form
            if (data.shipment_uuid) {
                const uuidEl = document.getElementById('shipment-uuid');
                if (uuidEl) uuidEl.value = data.shipment_uuid;
            }

            // Connect SSE stream (main.js exports startStream / window.startSSEStream)
            if (typeof window.startSSEStream === 'function') {
                window.startSSEStream(data.session_id, data.stream_url);
            } else if (typeof startSSEStream === 'function') {
                startSSEStream(data.session_id, data.stream_url);
            } else {
                // Fallback: directly open EventSource
                const es = new EventSource(data.stream_url);
                es.onmessage = function(ev) {
                    try { window._handleSSEData && window._handleSSEData(JSON.parse(ev.data)); } catch(e){}
                };
                es.addEventListener('done', () => es.close());
            }

        } catch(err) {
            errBox.textContent = 'Network error: ' + err.message;
            errBox.classList.remove('hidden');
        } finally {
            btnTxt.textContent = '⚡ Analyse & Simulate Route';
            spin?.classList.add('hidden');
            if (btn) btn.disabled = false;
        }
    });
});
</script>
"""

# Insert before </body>
content = content.replace('</body></html>', new_js + '\n</body></html>')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('JS injected successfully')
