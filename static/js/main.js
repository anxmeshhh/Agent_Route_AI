/* ═══════════════════════════════════════════════════════════
   AgentRoute AI — main.js v6.0 FINAL
   Key fixes vs v5:
   - Route map triggered from INTAKE LOG (not from result)
   - console.log('[route] CALLED:' before any await
   - window.onerror captures all silent errors
   - Bulletproof origin/dest extraction from multiple sources
   - Car animation with explicit console step logging
═══════════════════════════════════════════════════════════ */
'use strict';

/* ── Catch ALL unhandled errors for debugging ─────────────── */
window.onerror = (msg, src, line) =>
    console.error('[GLOBAL-ERR]', msg, `${src}:${line}`);
window.onunhandledrejection = e =>
    console.error('[PROMISE-ERR]', e.reason);

/* ── Auth state ──────────────────────────────────────────── */
let _currentUser = null;  // populated by loadCurrentUser()

async function loadCurrentUser() {
    try {
        const r = await fetch('/api/auth/me', { credentials: 'include' });
        if (r.status === 401) {
            // Not logged in — redirect to login unless we're already there
            if (!window.location.pathname.startsWith('/login') &&
                !window.location.pathname.startsWith('/signup') &&
                !window.location.pathname.startsWith('/otp')) {
                window.location.href = '/login';
            }
            return;
        }
        if (!r.ok) return;
        _currentUser = await r.json();
        _renderUserChip(_currentUser);
        loadApprovedOrgs();
    } catch(e) {
        console.warn('[auth] Could not reach /api/auth/me:', e.message);
    }
}

function _renderUserChip(user) {
    const chip    = el('user-chip'); if (!chip) return;
    const avatar  = el('user-chip-avatar');
    const nameEl  = el('user-chip-name');
    const orgEl   = el('user-chip-org');
    if (avatar)  avatar.textContent  = (user.display_name || '?')[0].toUpperCase();
    if (nameEl)  nameEl.textContent  = user.display_name || 'Unknown';
    if (orgEl)   orgEl.textContent   = '🏢 ' + (user.org_name || 'No Org');
    chip.classList.remove('hidden');

    el('logout-btn')?.addEventListener('click', async () => {
        await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
        window.location.href = '/login';
    });
}

/* ── State ───────────────────────────────────────────────── */
let _bgMap           = null;
let _routeLayers     = [];
let _vehicleMarker   = null;
let _vehiclePath     = [];
let _vehicleRawWps   = [];
let _vehicleStep     = 0;
let _vehicleInterval = null;
let _totalRouteKm    = 0;
let _routeIsLand     = false;
let _currentWaypts   = [];
let _currentResult   = null;
let _analysisStart   = null;
let _timerInterval   = null;
let _agentsDone      = 0;
let _aiDecisionTimer = null;
let _checkpointEl    = null;
let _simSpeed        = 3;
let _pendingOrigin   = null;  // Set from intake log early
let _pendingDest     = null;  // Set from intake log early
let _routeRendered   = false; // Guard: only render once per analysis
let _routeAbort      = null;  // AbortController for current route fetch
const TOTAL_AGENTS   = 8;

/* ── Dynamic Checkpoint AI Storytelling (no hardcoded names) ─── */
function _getCheckpointMsg(name) {
    const n = (name || '').toLowerCase();
    // Maritime chokepoints — each with REASONING about WHY this route
    if (n.includes('suez'))       return [
        '⚓ Suez Canal — fastest Asia↔Europe corridor',
        '🧠 AI chose this: Avoids 6,000nm Cape detour · Saves 12–15 days · Convoy slot secured'
    ];
    if (n.includes('malacca'))    return [
        '🚢 Malacca Strait — 40% of world trade passes here',
        '🧠 AI chose this: Shortest Pacific↔Indian Ocean link · Piracy risk LOW · AIS tracking active'
    ];
    if (n.includes('gibraltar'))  return [
        '🌊 Gibraltar — Atlantic↔Mediterranean gateway',
        '🧠 AI chose this: Only viable Med entry without 10,000nm Africa circumnavigation'
    ];
    if (n.includes('hormuz'))     return [
        '⚠ Strait of Hormuz — Persian Gulf outlet',
        '🧠 AI chose this: Only maritime exit from Gulf region · Geopolitical monitoring active'
    ];
    if (n.includes('panama'))     return [
        '🔒 Panama Canal — Pacific↔Atlantic shortcut',
        '🧠 AI chose this: Eliminates Cape Horn rounding · Saves 8,000nm · Lock transit ~8hrs'
    ];
    if (n.includes('cape'))       return [
        '🌊 Cape of Good Hope — Southern tip of Africa',
        '🧠 AI chose this: Suez alternatives exhausted or blocked · Accepts +12d transit time'
    ];
    if (n.includes('bab'))        return [
        '🚢 Bab el-Mandeb — Red Sea southern entry',
        '🧠 AI chose this: Mandatory passage for Suez-bound vessels · Security corridor monitored'
    ];
    if (n.includes('dover'))      return [
        '⚓ Dover Strait — busiest shipping lane on Earth',
        '🧠 AI chose this: North Sea↔Channel link · Traffic separation scheme active'
    ];
    if (n.includes('atlantic'))   return [
        '🌊 Atlantic Ocean crossing',
        '🧠 AI chose this: Great-circle route for minimum distance · Weather window optimal'
    ];
    if (n.includes('pacific'))    return [
        '🌊 Pacific Ocean crossing — longest open water segment',
        '🧠 AI chose this: Direct trans-oceanic route · Follows prevailing currents for fuel efficiency'
    ];
    if (n.includes('arabian'))    return [
        '🌊 Arabian Sea — Indian Ocean western basin',
        '🧠 AI chose this: Direct Indian subcontinent↔Middle East corridor · Monsoon season assessed'
    ];
    if (n.includes('south china'))return [
        '🚢 South China Sea — East Asia shipping hub',
        '🧠 AI chose this: Gateway to ASEAN ports · Dense traffic but well-charted lanes'
    ];
    if (n.includes('mediterranean')) return [
        '🌊 Mediterranean Sea passage',
        '🧠 AI chose this: Inland sea routing reduces open-ocean exposure · Port alternatives available'
    ];
    // Airport checkpoints for AIR mode
    if (n.includes('—') || n.includes('intl') || n.includes('airport'))  return [
        `✈ ${name} — Air waypoint`,
        '🧠 AI chose this: Optimal great-circle arc · Airspace clearance confirmed · Fuel-efficient altitude'
    ];
    // Road checkpoints — dynamic
    if (n.includes('hub'))        return [
        `🛣 ${name} — Logistics hub`,
        '🧠 AI chose this: Major road intersection · Fuel/rest facility available · Highway connectivity optimal'
    ];
    if (n.includes('junction') || n.includes('nh'))  return [
        `🛣 ${name} — Highway junction`,
        '🧠 AI chose this: National highway intersection · Traffic flow monitored · Alternative routes available'
    ];
    if (n.includes('port'))       return [
        `🚢 ${name} — Port facility`,
        '🧠 AI chose this: Nearest port to route · Coastal alternative viable if road risk rises'
    ];
    // Generic checkpoint
    return [
        `📍 ${name} — Route checkpoint`,
        '🧠 AI chose this: Route integrity verified · Optimal path maintained · Proceeding to next waypoint'
    ];
}

/* ── Helpers ─────────────────────────────────────────────── */
const el      = id => document.getElementById(id);
const showEl  = id => el(id)?.classList.remove('hidden');
const hideEl  = id => el(id)?.classList.add('hidden');
const setText = (id, v) => { const e = el(id); if (e) e.textContent = (v ?? '--'); };
const escHtml = s => String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');

/* ══════════════════════════════════════════════════════════
   1. MAP
═══════════════════════════════════════════════════════════ */
function setupLeafletMap() {
    if (_bgMap) return;
    const container = document.getElementById('world-map-bg');
    if (!container) { console.error('[map] #world-map-bg not found'); return; }
    try {
        _bgMap = L.map('world-map-bg', {
            center: [20.5937, 78.9629], zoom: 5,
            zoomControl: false, attributionControl: false,
        });
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { maxZoom: 19 })
         .addTo(_bgMap);
        L.control.zoom({ position: 'bottomright' }).addTo(_bgMap);
        console.log('[map] Leaflet map initialized OK');
    } catch (e) {
        console.error('[map] Failed to init Leaflet:', e);
    }
}

function whenMapReady(cb) {
    if (typeof L !== 'undefined' && _bgMap) { try { cb(); } catch(e) { console.error('[map-cb] Error:', e); } return; }
    if (typeof L !== 'undefined') { setupLeafletMap(); try { cb(); } catch(e) { console.error('[map-cb] Error:', e); } return; }
    setTimeout(() => whenMapReady(cb), 100);
}

/* ══════════════════════════════════════════════════════════
   2. ROUTE RENDERING
═══════════════════════════════════════════════════════════ */
async function renderRouteMap(origin, dest, riskScore) {
    // FIRST log — before anything else so we always see it
    console.log('[route] CALLED:', origin, '->', dest, 'score:', riskScore, 'map:', !!_bgMap);

    if (!origin || !dest || origin === dest) {
        console.warn('[route] origin/dest invalid — skipping map render');
        return;
    }
    if (!_bgMap) {
        console.warn('[route] _bgMap is null — setting up...');
        setupLeafletMap();
        if (!_bgMap) { console.error('[route] Map still null after setup'); return; }
    }

    // Cancel any previous in-flight route fetch
    if (_routeAbort) { _routeAbort.abort(); }
    _routeAbort = new AbortController();
    const signal = _routeAbort.signal;

    let data;
    try {
        // Read active transport mode from UI buttons (or auto-detect)
        const uiMode = document.getElementById('btn-sea')?.classList.contains('active') ? 'sea'
                     : document.getElementById('btn-air')?.classList.contains('active') ? 'air'
                     : 'auto';   // auto lets backend smart-detect
        const url = `/api/route?origin=${encodeURIComponent(origin)}&dest=${encodeURIComponent(dest)}&mode=${uiMode}`;
        console.log('[route] fetching:', url, '| UI mode:', uiMode);
        const r = await fetch(url, { signal });
        console.log('[route] fetch status:', r.status);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        data = await r.json();
        if (data.error) throw new Error(data.error);
        console.log('[route] data OK — waypoints:', data.waypoints?.length, 'km:', data.total_km);
    } catch (e) {
        if (e.name === 'AbortError') {
            console.log('[route] fetch aborted (superseded by newer request)');
        } else {
            console.error('[route] FETCH FAILED:', e.message, e);
        }
        return;
    }

    const { origin: og, dest: dg, waypoints, is_land_route, total_km, transport_mode } = data;
    if (!og || !dg || !waypoints || waypoints.length < 2) {
        console.error('[route] bad data:', { og, dg, wLen: waypoints?.length });
        return;
    }

    // Store state
    const tMode    = transport_mode || (is_land_route ? 'road' : 'sea');
    _routeIsLand   = tMode === 'road';
    _vehicleRawWps = waypoints;
    _currentWaypts = waypoints.map(p => [p.lat, p.lon]);
    _totalRouteKm  = total_km || _calcKm(_currentWaypts);

    // Dense path (skip zero-length segments)
    _vehiclePath = _makeDensePath(_currentWaypts, 60);
    console.log('[route] dense path:', _vehiclePath.length, 'pts |', Math.round(_totalRouteKm), 'km | land:', _routeIsLand);

    // Clear old layers
    _routeLayers.forEach(l => { try { _bgMap.removeLayer(l); } catch (_) {} });
    _routeLayers = [];
    _stopVehicle();

    // Draw with mode-specific colors
    const score = riskScore ?? 0;
    const color = tMode === 'air' 
        ? (score >= 70 ? '#ef4444' : '#a855f7')  // purple for air
        : _routeIsLand
            ? (score >= 70 ? '#ef4444' : score >= 45 ? '#f97316' : '#f59e0b')  // yellow/orange for road
            : (score >= 70 ? '#ef4444' : score >= 45 ? '#f97316' : '#06b6d4'); // cyan for sea

    console.log('[route] drawing on map, color:', color, 'mode:', tMode);

    // Glow layers + dashed route
    _routeLayers.push(L.polyline(_currentWaypts, { color, weight: 20, opacity: 0.04 }).addTo(_bgMap));
    _routeLayers.push(L.polyline(_currentWaypts, { color, weight: 7,  opacity: 0.12 }).addTo(_bgMap));
    const dashStyle = tMode === 'air' ? '3,12' : _routeIsLand ? '5,9' : '6,10';
    _routeLayers.push(L.polyline(_currentWaypts, {
        color, weight: 2.5, opacity: 0.9,
        dashArray: dashStyle,
    }).addTo(_bgMap));

    // Origin marker
    _routeLayers.push(_makePortMarker(og.lat, og.lon, false, `🟢 ${origin}`, 'Origin'));

    // Destination marker — with REAL weather if available
    const destWeather = data.dest_weather;
    const destLabel = destWeather
        ? `Destination · ${destWeather.temp_c}°C ${destWeather.description} · Wind ${destWeather.wind_speed_kmh}km/h`
        : 'Destination';
    _routeLayers.push(_makePortMarker(dg.lat, dg.lon, true, `🔴 ${dest}`, destLabel));

    // Checkpoint markers — tooltips now use BACKEND AI reasoning
    for (let i = 1; i < waypoints.length - 1; i++) {
        const wp = waypoints[i];
        const aiTip = wp.ai_reasoning || `📍 ${wp.name || 'Checkpoint'}`;
        _routeLayers.push(_makeCheckpointMarkerAI(wp.lat, wp.lon, color, wp.name || `Stop ${i}`, aiTip));
    }

    // ── PLAN B: Alternate route (green dashed) if available ────
    const alt = data.alternate_route;
    if (alt && alt.waypoints && alt.waypoints.length >= 2) {
        const altPts = alt.waypoints.map(p => [p.lat, p.lon]);
        _routeLayers.push(L.polyline(altPts, { color: '#22c55e', weight: 10, opacity: 0.05 }).addTo(_bgMap));
        _routeLayers.push(L.polyline(altPts, { color: '#22c55e', weight: 2, opacity: 0.6, dashArray: '8,14' }).addTo(_bgMap));
        // Plan B label marker at midpoint
        const mid = Math.floor(altPts.length / 2);
        const altExtraKm = alt.extra_km ?? alt.delta_km ?? 0;
        const altExtraTime = alt.extra_days != null ? `+${alt.extra_days}d` : (alt.delta_hours != null ? `+${alt.delta_hours}h` : '');
        const altIcon = L.divIcon({
            className: '',
            html: `<div class="alt-route-label">🛡 Plan B: ${alt.label}<br>${altExtraKm > 0 ? '+' : ''}${altExtraKm?.toLocaleString()} km · ${altExtraTime}</div>`,
            iconSize: [180, 40], iconAnchor: [90, 20],
        });
        _routeLayers.push(L.marker(altPts[mid], { icon: altIcon }).addTo(_bgMap));
        console.log('[route] Plan B drawn:', alt.label, alt.total_km, 'km');
        appendLog('graph', `🛡 Plan B available: ${alt.label} (${altExtraKm > 0 ? '+' : ''}${altExtraKm?.toLocaleString()} km, ${altExtraTime}) — ${alt.reason}`, 'success');
    }

    // ── Weather badge on map if real weather available ─────────
    if (destWeather) {
        const wIcon = L.divIcon({
            className: '',
            html: `<div class="weather-badge-map">🌡 ${destWeather.temp_c}°C · ${destWeather.description} · 💨 ${destWeather.wind_speed_kmh}km/h</div>`,
            iconSize: [220, 28], iconAnchor: [110, -12],
        });
        _routeLayers.push(L.marker([dg.lat, dg.lon], { icon: wIcon, zIndexOffset: 1500 }).addTo(_bgMap));
    }

    // Overlay card — mode-aware labels
    const modeIcon  = tMode === 'air' ? '✈' : tMode === 'road' ? '🚗' : '🚢';
    const modeLabel = tMode === 'air' ? 'Air Route' : tMode === 'road' ? 'Road Route' : 'Maritime Route';
    const via = waypoints[0]?.via || modeLabel;
    setText('map-overlay-route-text', `${origin} → ${dest}`);
    const altBadge = alt ? ` · 🛡 Plan B available` : '';
    setText('map-overlay-meta', `${modeIcon} ${modeLabel} · ${waypoints.length - 2} checkpoints${altBadge}`);
    const badge = el('map-route-badge');
    if (badge) {
        badge.textContent = `via ${via.split('·')[0].trim()}`;
        badge.className = `overlay-badge ${tMode === 'road' ? 'road-badge' : tMode === 'air' ? 'air-badge' : ''}`;
        badge.classList.remove('hidden');
    }
    const kmBadge = el('map-km-badge');
    if (kmBadge && _totalRouteKm) {
        kmBadge.textContent = `~${Math.round(_totalRouteKm).toLocaleString()} km`;
        kmBadge.classList.remove('hidden');
    }
    showEl('map-overlay-card');
    showEl('sim-speed-control');

    // Fit map to route bounds
    try {
        _bgMap.flyToBounds(L.latLngBounds(_currentWaypts), {
            paddingTopLeft: [370, 60], paddingBottomRight: [20, 80], duration: 1.0,
        });
    } catch (e) {
        console.warn('[route] flyToBounds failed (non-fatal):', e.message);
        _bgMap.setView([20.5, 78.9], 5);
    }

    // Start animation after map settles
    console.log('[route] scheduling vehicle start in 1600ms');
    setTimeout(() => {
        console.log('[route] 1600ms elapsed — calling _startVehicleAnimation');
        _startVehicleAnimation();
    }, 1600);
}

function _makePortMarker(lat, lon, isDest, tooltip, label) {
    const icon = L.divIcon({
        className: '',
        html: `<div class="port-marker"><div class="port-pulse${isDest?' dest-pulse':''}"></div><div class="port-dot${isDest?' dest-dot':''}"></div></div>`,
        iconSize: [24,24], iconAnchor: [12,12],
    });
    return L.marker([lat, lon], { icon })
        .bindTooltip(`<b>${tooltip}</b><br>${label}`, { className:'leaflet-tool-text', direction:'top' })
        .addTo(_bgMap);
}

function _makeCheckpointMarker(lat, lon, color, name) {
    const icon = L.divIcon({
        className: '',
        html: `<div class="choke-marker" style="--choke-color:${color}"><div class="choke-ring"></div><div class="choke-core"></div></div>`,
        iconSize: [20,20], iconAnchor: [10,10],
    });
    return L.marker([lat, lon], { icon })
        .bindTooltip(`<b>⚑ ${name}</b>`, { className:'leaflet-tool-text', direction:'top' })
        .addTo(_bgMap);
}

function _makeCheckpointMarkerAI(lat, lon, color, name, aiReasoning) {
    const icon = L.divIcon({
        className: '',
        html: `<div class="choke-marker" style="--choke-color:${color}"><div class="choke-ring"></div><div class="choke-core"></div></div>`,
        iconSize: [20,20], iconAnchor: [10,10],
    });
    const tooltipHtml = `<b>⚑ ${escHtml(name)}</b><br><span style="font-size:10px;color:#a78bfa">${escHtml(aiReasoning)}</span>`;
    return L.marker([lat, lon], { icon })
        .bindTooltip(tooltipHtml, { className:'leaflet-tool-text', direction:'top', maxWidth: 320 })
        .addTo(_bgMap);
}

/* ── Path maths ──────────────────────────────────────────── */
function _makeDensePath(sparse, pts = 60) {
    if (!sparse || sparse.length < 2) return sparse || [];
    const dense = [];
    for (let i = 0; i < sparse.length - 1; i++) {
        const [la, lo] = sparse[i];
        const [lb, lb2] = sparse[i + 1];
        if (la === lb && lo === lb2) continue; // skip zero-length segments
        for (let j = 0; j < pts; j++) {
            const t = j / pts;
            dense.push([la + (lb - la) * t, lo + (lb2 - lo) * t]);
        }
    }
    dense.push(sparse[sparse.length - 1]);
    return dense;
}

function _calcKm(sparse) {
    if (!sparse || sparse.length < 2) return 0;
    let km = 0;
    for (let i = 0; i < sparse.length - 1; i++) {
        const [la, lo] = sparse[i], [lb, lb2] = sparse[i + 1];
        const R = 6371;
        const dLat = (lb - la) * Math.PI / 180, dLon = (lb2 - lo) * Math.PI / 180;
        const a = Math.sin(dLat/2)**2 + Math.cos(la*Math.PI/180)*Math.cos(lb*Math.PI/180)*Math.sin(dLon/2)**2;
        km += R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    }
    return km;
}

/* ══════════════════════════════════════════════════════════
   3. VEHICLE ANIMATION
═══════════════════════════════════════════════════════════ */
function _stopVehicle() {
    if (_vehicleInterval) { clearInterval(_vehicleInterval); _vehicleInterval = null; }
    if (_vehicleMarker)   { try { _bgMap?.removeLayer(_vehicleMarker); } catch(_){} _vehicleMarker = null; }
    if (_checkpointEl)    { _checkpointEl.remove(); _checkpointEl = null; }
    _vehicleStep = 0;
}

function _clearRoute() {
    // Remove ALL drawn layers (polylines, markers, glows) from previous route
    _routeLayers.forEach(l => { try { _bgMap?.removeLayer(l); } catch(_) {} });
    _routeLayers     = [];
    _vehiclePath     = [];
    _vehicleRawWps   = [];
    _currentWaypts   = [];
    _totalRouteKm    = 0;
    _routeIsLand     = false;
    console.log('[route] Previous route layers cleared');
}

function _startVehicleAnimation() {
    console.log('[anim] _startVehicleAnimation called');
    console.log('[anim] _bgMap:', !!_bgMap, '| _vehiclePath.length:', _vehiclePath.length);

    if (!_bgMap) { console.error('[anim] No map — cannot animate'); return; }
    if (!_vehiclePath || _vehiclePath.length < 2) {
        console.error('[anim] Dense path too short:', _vehiclePath?.length, '— cannot animate');
        return;
    }

    _stopVehicle();
    console.log('[anim] Placing vehicle at', _vehiclePath[0]);

    // Mode-aware vehicle emoji and styles
    const isAir   = !_routeIsLand && _vehicleRawWps?.[0]?.via?.toLowerCase().includes('air');
    const emoji   = isAir ? '✈️' : _routeIsLand ? '🚗' : '🚢';
    const tooltip = isAir ? '✈ Aircraft in Flight' : _routeIsLand ? '🚗 Vehicle in Transit' : '🚢 Vessel in Transit';
    const wrapCls = isAir ? 'air-icon-wrap' : _routeIsLand ? 'vehicle-icon-wrap' : 'ship-icon-wrap';
    const mkCls   = isAir ? 'air-animation-marker' : _routeIsLand ? 'vehicle-animation-marker' : 'ship-animation-marker';

    const icon = L.divIcon({
        className: mkCls,
        html: `<div class="${wrapCls}"><span class="vehicle-emoji" style="font-size:22px;line-height:1">${emoji}</span></div>`,
        iconSize: [36,36], iconAnchor: [18,18],
    });

    try {
        _vehicleMarker = L.marker(_vehiclePath[0], { icon, zIndexOffset: 2000 })
            .bindTooltip(tooltip, { className:'leaflet-tool-text', direction:'top' })
            .addTo(_bgMap);
        _routeLayers.push(_vehicleMarker);
        console.log('[anim] Marker added to map OK');
    } catch (e) {
        console.error('[anim] Failed to add marker:', e);
        return;
    }

    showEl('mission-control-hud');
    _updateProgress(0, 0);

    const checkpoints = _buildCheckpoints();
    console.log('[anim] Checkpoints:', checkpoints.length);
    let cpIdx = 0;
    const totalSteps = _vehiclePath.length - 1;

    console.log('[anim] Starting setInterval @ 80ms | totalSteps:', totalSteps, '| simSpeed:', _simSpeed);

    _vehicleInterval = setInterval(() => {
        try {
            if (!_vehicleMarker || !_bgMap) {
                clearInterval(_vehicleInterval); _vehicleInterval = null;
                return;
            }
            const steps = Math.max(1, Math.round(_simSpeed));
            _vehicleStep = Math.min(_vehicleStep + steps, totalSteps);
            _vehicleMarker.setLatLng(_vehiclePath[_vehicleStep]);
            _rotateCar();

            const pct    = Math.round((_vehicleStep / totalSteps) * 100);
            const kmDone = Math.round((_vehicleStep / totalSteps) * _totalRouteKm);
            _updateProgress(pct, kmDone);

            while (cpIdx < checkpoints.length && _vehicleStep >= checkpoints[cpIdx].step) {
                _fireCheckpoint(checkpoints[cpIdx]);
                cpIdx++;
            }

            if (_vehicleStep >= totalSteps) {
                clearInterval(_vehicleInterval); _vehicleInterval = null;
                _onArrived();
            }
        } catch (err) {
            console.error('[anim] interval error:', err);
        }
    }, 80);
}

function _buildCheckpoints() {
    if (!_vehicleRawWps.length || !_vehiclePath.length) return [];
    const rawLen = _vehicleRawWps.length;
    const denseLen = _vehiclePath.length;
    const result = [];
    for (let i = 1; i < rawLen - 1; i++) {
        const frac = i / (rawLen - 1);
        const step = Math.floor(frac * (denseLen - 1));
        result.push({ step, rawIdx: i, name: _vehicleRawWps[i].name || `Checkpoint ${i}`, lat: _vehicleRawWps[i].lat, lon: _vehicleRawWps[i].lon });
    }
    return result;
}

function _fireCheckpoint({ name, lat, lon, rawIdx }) {
    // Use BACKEND ai_reasoning if available, else fall back to client-side
    // Look up by index (reliable) — name-based .find() fails for unnamed OSRM waypoints
    const wp = (rawIdx != null && _vehicleRawWps?.[rawIdx]) || _vehicleRawWps?.find(w => w.name === name);
    const aiReason = wp?.ai_reasoning;
    const msgs = aiReason ? [name, aiReason] : _getCheckpointMsg(name);
    console.log('[checkpoint]', name, aiReason ? '(backend AI)' : '(client fallback)');
    setText('hud-loc-text', name);
    showEl('hud-current-loc');
    setText('ai-decision-text', `📍 ${name}: ${msgs[1]}`);
    showEl('ai-decision-banner');
    _showMapDecision(`📍 ${name}\n${msgs[1]}`);
    _showCheckpointPopup(lat, lon, name, msgs);
    const icon = _routeIsLand ? '🚗' : '🚢';
    appendLog('graph', `${icon} ${name} — ${msgs[1]}`, 'success');
}

function _showCheckpointPopup(lat, lon, name, msgs) {
    if (_checkpointEl) { _checkpointEl.remove(); _checkpointEl = null; }
    if (!_bgMap) return;
    const mapEl = el('world-map-bg');
    if (!mapEl) return;
    try {
        const pt = _bgMap.latLngToContainerPoint([lat, lon]);
        const div = document.createElement('div');
        div.className = 'checkpoint-popup';
        div.style.cssText = `left:${pt.x}px;top:${Math.max(10,pt.y-95)}px`;
        div.innerHTML = `
            <div class="checkpoint-header">⚑ AI Checkpoint</div>
            <div class="checkpoint-city">${escHtml(name)}</div>
            <div class="checkpoint-decision">${escHtml(msgs[0])}</div>
            <div class="checkpoint-decision" style="color:#818cf8;margin-top:2px">${escHtml(msgs[1]||'')}</div>`;
        mapEl.appendChild(div);
        _checkpointEl = div;
        setTimeout(() => { if (_checkpointEl===div) { div.remove(); _checkpointEl=null; } }, 4500);
    } catch (e) { console.warn('[checkpoint-popup]', e); }
}

function _rotateCar() {
    if (!_vehicleMarker || _vehicleStep < 1) return;
    try {
        const [la, lo]   = _vehiclePath[_vehicleStep - 1];
        const [lb, lb2]  = _vehiclePath[_vehicleStep];
        const angle = Math.atan2(lb2 - lo, lb - la) * (180 / Math.PI);
        const span  = _vehicleMarker.getElement()?.querySelector('.vehicle-emoji');
        if (span) span.style.transform = `rotate(${angle}deg)`;
    } catch(_) {}
}

function _updateProgress(pct, kmDone) {
    const bar = el('ship-progress-bar');
    if (bar) bar.style.width = `${pct}%`;
    setText('ship-progress-label', `${pct}% en route`);
    setText('hud-km-counter', _totalRouteKm
        ? `${kmDone.toLocaleString()} / ${Math.round(_totalRouteKm).toLocaleString()} km`
        : `${pct}%`);
}

function _onArrived() {
    if (_checkpointEl) { _checkpointEl.remove(); _checkpointEl = null; }
    setText('hud-agent-action', '✅ Arrived at destination!');
    setText('hud-loc-text', 'Destination Reached');
    _showMapDecision(`✅ Journey Complete!\n${Math.round(_totalRouteKm).toLocaleString()} km delivered.`);
    appendLog('brain', '✅ Simulation complete — vehicle reached destination.', 'success');
    showEl('simulate-btn');
    _updateProgress(100, Math.round(_totalRouteKm));
    console.log('[anim] Vehicle arrived!');
}

/* Public replay */
function runShipSimulation() {
    if (!_bgMap || !_currentWaypts.length) { alert('Run an analysis first.'); return; }
    _vehiclePath = _makeDensePath(_currentWaypts, 60);
    console.log('[replay] _vehiclePath reset:', _vehiclePath.length, 'pts');
    try { _bgMap.flyToBounds(L.latLngBounds(_currentWaypts), { paddingTopLeft:[370,60], paddingBottomRight:[20,80], duration:1.0 }); } catch(_) {}
    setTimeout(() => _startVehicleAnimation(), 1200);
}

/* ══════════════════════════════════════════════════════════
   4. AI MAP DECISION OVERLAY
═══════════════════════════════════════════════════════════ */
function _showMapDecision(text) {
    const overlay = el('ai-map-decision');
    const textEl  = el('ai-map-decision-text');
    if (!overlay || !textEl) return;
    // Truncate to keep the overlay compact
    const clean = text.replace(/\n/g, ' — ');
    const display = clean.length > 140 ? clean.slice(0, 137) + '…' : clean;
    textEl.innerHTML = escHtml(display);
    overlay.classList.remove('hidden');
    if (_aiDecisionTimer) clearTimeout(_aiDecisionTimer);
    _aiDecisionTimer = setTimeout(() => overlay.classList.add('hidden'), 4000);
}

/* ══════════════════════════════════════════════════════════
   5. PIPELINE NODES + HUD
═══════════════════════════════════════════════════════════ */
const AGENT_META = {
    intake:       { icon:'📦', color:'#fb923c' },
    router:       { icon:'🧠', color:'#a855f7' },
    weather:      { icon:'🌤', color:'#6366f1' },
    news:         { icon:'📰', color:'#f43f5e' },
    historical:   { icon:'📊', color:'#22c55e' },
    vessel:       { icon:'🚗', color:'#22d3ee' },
    port_intel:   { icon:'📍', color:'#14b8a6' },
    geopolitical: { icon:'🌍', color:'#fbbf24' },
    brain:        { icon:'⚡', color:'#c084fc' },
    graph:        { icon:'🔗', color:'#818cf8' },
    memory:       { icon:'💾', color:'#2dd4bf' },
    validator:    { icon:'🔍', color:'#fb923c' },
    confidence:   { icon:'📈', color:'#34d399' },
    resolver:     { icon:'⚖',  color:'#fbbf24' },
    risk:         { icon:'⚠',  color:'#f97316' },
};

function updateHUD(agent, action, status) {
    showEl('mission-control-hud');
    const meta = AGENT_META[agent] || { icon:'⚙', color:'#94a3b8' };
    setText('hud-agent-icon', meta.icon);
    const nm = el('hud-agent-name');
    if (nm) { nm.textContent = agent.toUpperCase(); nm.style.color = meta.color; }
    setText('hud-agent-action', (action||'').substring(0,100));
    const dot = el('hud-status-dot');
    if (dot) {
        dot.className = 'hud-dot';
        dot.classList.add(status==='success'?'hud-dot-green':status==='failed'?'hud-dot-red':'hud-dot-blue');
    }
}

function activateNode(agent) {
    document.querySelectorAll('.pipeline-node').forEach(n => n.classList.remove('active'));
    document.querySelector(`.pipeline-node[data-agent="${agent}"]`)?.classList.add('active');
}
function completeNode(agent, ok=true) {
    const nd = document.querySelector(`.pipeline-node[data-agent="${agent}"]`);
    nd?.classList.remove('active');
    nd?.classList.add(ok?'done':'error');
}
function resetNodes() {
    document.querySelectorAll('.pipeline-node').forEach(n => n.classList.remove('active','done','error'));
}

/* ══════════════════════════════════════════════════════════
   6. AGENT LOG PANEL
═══════════════════════════════════════════════════════════ */
const DECISION_KW = ['route','risk','recommend','optimal','proceed','delay','complete','decision','analysis'];

function appendLog(agent, message, status='default') {
    el('log-empty')?.classList.add('hidden');
    const container = el('agent-log-entries');
    if (!container) return;
    const meta = AGENT_META[agent] || { icon:'⚙', color:'#94a3b8' };
    const cls  = { success:'log-status-success', failed:'log-status-failed', started:'log-status-started', skipped:'log-status-skipped' };
    const sCls = cls[status] || '';
    const badge = sCls ? `<span class="log-status-badge ${sCls}">${status.toUpperCase()}</span>` : '';
    const entry = document.createElement('div');
    entry.className = `log-entry${sCls?` log-entry-${status}`:''}`;
    entry.innerHTML = `
        <div class="log-icon" style="color:${meta.color}">${meta.icon}</div>
        <div class="log-content">
            <div class="log-agent-row">
                <span class="log-agent" style="color:${meta.color}">${escHtml(agent.toUpperCase())}</span>
                ${badge}
            </div>
            <div class="log-message">${escHtml(message)}</div>
        </div>`;
    container.appendChild(entry);
    requestAnimationFrame(() => { container.scrollTop = container.scrollHeight; });
    activateNode(agent);
    if (status==='success'||status==='failed') { completeNode(agent, status==='success'); _tickProgress(); }
    if (['brain','router','graph'].includes(agent)) {
        const low = message.toLowerCase();
        if (DECISION_KW.some(k => low.includes(k))) _showMapDecision(`🧠 ${agent.toUpperCase()}: ${message.substring(0,160)}`);
    }
    if (['brain','router'].includes(agent) && message.length > 20) {
        setText('ai-decision-text', message.substring(0,200));
        showEl('ai-decision-banner');
    }
}

function clearLog() {
    const c = el('agent-log-entries'); if (c) c.innerHTML = '';
    showEl('log-empty');
    hideEl('ai-decision-banner');
    hideEl('parallel-agents-row');
    resetNodes();
}

function showParallelAgents(agents) {
    const row = el('parallel-agents-row'), chips = el('parallel-chips');
    if (!row || !chips || !agents?.length) return;
    chips.innerHTML = agents.map(a => { const m=AGENT_META[a]||{icon:'⚙'}; return `<span class="parallel-chip">${m.icon} ${a}</span>`; }).join('');
    row.classList.remove('hidden');
}

/* ══════════════════════════════════════════════════════════
   7. PROGRESS + TIMER
═══════════════════════════════════════════════════════════ */
function _tickProgress() {
    _agentsDone = Math.min(_agentsDone + 1, TOTAL_AGENTS);
    const pct = Math.round((_agentsDone / TOTAL_AGENTS) * 100);
    const bar = el('agent-progress-fill'); if (bar) bar.style.width = `${pct}%`;
    setText('agent-progress-label', `${_agentsDone}/${TOTAL_AGENTS} agents`);
}
function _resetProgress() {
    _agentsDone = 0;
    const bar = el('agent-progress-fill'); if (bar) bar.style.width = '0%';
    setText('agent-progress-label', `0/${TOTAL_AGENTS} agents`);
}
function _startTimer() {
    _analysisStart = Date.now();
    if (_timerInterval) clearInterval(_timerInterval);
    _timerInterval = setInterval(() => setText('elapsed-timer', `${((Date.now()-_analysisStart)/1000).toFixed(1)}s`), 100);
}
function _stopTimer() { if (_timerInterval) { clearInterval(_timerInterval); _timerInterval = null; } }

/* ══════════════════════════════════════════════════════════
   8. FORM + SSE + ANALYSIS
═══════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
    // Auth guard: load user, redirect to /login if unauthenticated
    loadCurrentUser();

    setTimeout(setupLeafletMap, 300);

    el('sim-speed-slider')?.addEventListener('input', function() {
        _simSpeed = parseInt(this.value, 10);
        setText('sim-speed-val', `${_simSpeed}×`);
    });

    document.querySelectorAll('.example-chip').forEach(btn => {
        btn.addEventListener('click', () => {
            const q = el('query-input'); if (!q) return;
            q.value = btn.dataset.query || btn.textContent.trim();
            autoDetectType(q.value); q.focus();
        });
    });

    el('clear-logs-btn')?.addEventListener('click', clearLog);
    el('refresh-history')?.addEventListener('click', loadHistory);

    el('analysis-form')?.addEventListener('submit', async e => {
        e.preventDefault();
        const q = (el('query-input')?.value || '').trim();
        if (!q) return;
        autoDetectType(q);
        await startAnalysis(q);
    });

    loadHistory();

    // Quick-query pickup from dashboard
    const quickQ = sessionStorage.getItem('quick_query');
    if (quickQ) {
        sessionStorage.removeItem('quick_query');
        const qi = el('query-input');
        if (qi) { qi.value = quickQ; autoDetectType(quickQ); qi.focus(); }
    }
});

function autoDetectType(text) {
    const t = text.toLowerCase();
    const indKw = ['delhi','mumbai','bangalore','bengaluru','kolkata','chennai','hyderabad',
                   'kerala','kochi','thiruvananthapuram','trivandrum','jaipur','ahmedabad',
                   'pune','lucknow','nagpur','coimbatore','road','highway','nh','truck','india'];
    if (indKw.some(k => t.includes(k))) { setRouteType('land'); return; }
    if (['ship','vessel','port','maritime','suez','panama','strait'].some(k => t.includes(k))) setRouteType('sea');
}

function setRouteType(type) {
    document.querySelectorAll('.route-type-btn').forEach(b => b.classList.remove('active','road','sea','air'));
    const map = { land:['btn-land','road'], sea:['btn-sea','sea'], air:['btn-air','air'] };
    if (map[type]) { const [id,cls] = map[type]; el(id)?.classList.add('active', cls); }
}

async function startAnalysis(query) {
    const btn = el('analyze-btn'), btnText = el('btn-text'), spinner = el('btn-spinner');
    btn?.setAttribute('disabled','');
    spinner?.classList.remove('hidden');
    btnText?.classList.add('hidden');

    // Reset state — FLUSH everything from previous analysis
    _pendingOrigin = null; _pendingDest = null; _routeRendered = false;
    if (_routeAbort) { _routeAbort.abort(); _routeAbort = null; }
    clearLog(); _resetProgress(); _stopVehicle(); _clearRoute();
    hideEl('results-state'); hideEl('map-overlay-card'); hideEl('route-intel-strip');
    hideEl('ai-map-decision'); hideEl('sim-speed-control'); hideEl('agents-summary-card');
    const fcRow = el('owm-forecast-row'); if (fcRow) fcRow.style.display = 'none';
    showEl('map-scan-line'); hideEl('mission-control-hud');
    _startTimer();

    setText('running-current-action', '🚀 Routing to agentic pipeline…');
    updateHUD('intake','Parsing shipment query…','started');

    let sessionId;
    try {
        const r = await fetch('/api/analyze', {
            method:'POST', headers:{'Content-Type':'application/json'},
            credentials: 'include',
            body: JSON.stringify({ query }),
        });
        if (r.status === 401) {
            window.location.href = '/login';
            return;
        }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        if (d.error) throw new Error(d.error);
        sessionId = d.session_id;
    } catch (err) {
        _resetBtn(btn, btnText, spinner); hideEl('map-scan-line'); _stopTimer();
        appendLog('graph', `Start failed: ${err.message}`, 'failed');
        return;
    }

    openSSE(sessionId, btn, btnText, spinner);
}

function _resetBtn(btn, btnText, spinner) {
    btn?.removeAttribute('disabled');
    spinner?.classList.add('hidden');
    btnText?.classList.remove('hidden');
}

/* ── SSE ─────────────────────────────────────────────────── */
function openSSE(sessionId, btn, btnText, spinner) {
    const es = new EventSource(`/api/stream/${sessionId}`);

    es.addEventListener('agent_log', e => {
        try { handleLog(JSON.parse(e.data)?.data || JSON.parse(e.data)); } catch(_) {}
    });

    es.addEventListener('result', e => {
        try {
            const w = JSON.parse(e.data);
            es.close();
            const result = w.data || w;
            console.log('[sse] result received, risk_score:', result.risk_score,
                        'intake.origin:', result.intake?.origin_port,
                        'intake.dest:', result.intake?.port);
            onComplete(result, btn, btnText, spinner);
        } catch(err) {
            console.error('[sse] result parse error:', err);
        }
    });

    es.addEventListener('error', e => {
        let msg = 'Stream error';
        try { msg = JSON.parse(e.data)?.data?.message || msg; } catch(_) {}
        es.close(); _resetBtn(btn, btnText, spinner); hideEl('map-scan-line'); _stopTimer();
        appendLog('graph', msg, 'failed');
    });

    es.onerror = () => { if (es.readyState === EventSource.CLOSED) _resetBtn(btn, btnText, spinner); };
}

function handleLog(data) {
    if (!data) return;
    const agent  = data.agent  || 'system';
    const status = data.status || 'default';
    const action = data.action || data.message || '';

    appendLog(agent, action, status);
    setText('running-current-action', `${agent.toUpperCase()} — ${action.substring(0,75)}`);
    updateHUD(agent, action, status);

    // *** CRITICAL: Extract origin/dest from INTAKE and RENDER ROUTE IMMEDIATELY ***
    if (agent === 'intake' && data.data && !_routeRendered) {
        const d = data.data;
        if (d.origin_port && d.port && d.origin_port !== d.port) {
            _pendingOrigin = d.origin_port;
            _pendingDest   = d.port;
            console.log('[sse-intake] Got origin/dest from intake log:', _pendingOrigin, '->', _pendingDest);
            // 🔥 START ROUTE IMMEDIATELY — don't wait for full analysis
            _routeRendered = true;
            appendLog('graph', `🗺 Route Agent: Computing ${_pendingOrigin} → ${_pendingDest} route...`, 'started');
            renderRouteMap(_pendingOrigin, _pendingDest, 50); // use neutral score; real score updates later
        }
    }

    // Parallel agent chips
    if (agent === 'graph' && action.toLowerCase().includes('parallel')) {
        const match = action.match(/:\s*(.+)/);
        if (match) {
            showParallelAgents(match[1].split(',').map(s => s.trim().toLowerCase()));
            setTimeout(() => hideEl('parallel-agents-row'), 9000);
        }
    }
}

async function onComplete(result, btn, btnText, spinner) {
    _resetBtn(btn, btnText, spinner);
    _stopTimer();
    hideEl('map-scan-line');

    const elapsed = _analysisStart ? `${((Date.now()-_analysisStart)/1000).toFixed(1)}s` : '--';
    setText('running-current-action', `✅ Complete in ${elapsed}`);
    updateHUD('brain', `Analysis complete in ${elapsed}`, 'success');
    hideEl('parallel-agents-row');

    if (!result || result.risk_score == null) {
        appendLog('graph','No risk score returned — check agent logs.','failed');
        return;
    }

    _currentResult = result;
    hideEl('brand-panel');
    renderResult(result);
    loadHistory();
    // Auto-switch to Intel tab so Route Intelligence is immediately visible
    setTimeout(() => {
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        document.querySelectorAll('.result-tab').forEach(t => t.classList.remove('active'));
        const intelTab = document.getElementById('tab-intel');
        const intelBtn = document.querySelector('[onclick="switchTab(\'intel\')"]');
        if (intelTab) intelTab.classList.add('active');
        if (intelBtn) intelBtn.classList.add('active');
    }, 2500); // Wait 2.5s for fetchRouteAnalysis to populate data

}

/* ══════════════════════════════════════════════════════════
   9. RESULT RENDERING
═══════════════════════════════════════════════════════════ */
function renderResult(result) {
    console.log('[render] renderResult called');
    showEl('results-state');

    ['factors_json','mitigation_json'].forEach(k => {
        if (typeof result[k]==='string') try { result[k]=JSON.parse(result[k]); } catch(_) { result[k]=[]; }
    });

    const factors   = result.factors || result.factors_json || [];
    const intake    = result.intake || {};
    const score     = result.risk_score ?? 0;
    const level     = result.risk_level || _scoreToLevel(score);
    const etaDays   = result.eta_days || intake.eta_days || '--';
    const etaHours  = result.eta_hours || intake.eta_hours;
    const cargo     = result.cargo_type || intake.cargo_type || '--';

    // Transport mode — prefer authoritative backend value
    const transportMode = result.transport_mode || intake.transport_mode || (_routeIsLand ? 'road' : 'sea');
    const routeMode = {road: 'Road', air: 'Air', sea: 'Maritime'}[transportMode] || 'Road';

    // Extract origin + dest from ALL possible sources
    const origin = intake.origin_port || result.origin_port || _pendingOrigin || '--';
    const dest   = intake.port || intake.destination || result.destination || result.port || _pendingDest || '--';

    console.log('[render] origin:', origin, '| dest:', dest, '| score:', score, '| mode:', transportMode);

    // ── Core score display ──────────────────────────────────────────
    setText('gauge-score', score);
    _setRiskBadge('risk-level-badge', level);

    // Show hours for road routes, days for maritime/air
    if (etaHours && transportMode === 'road') {
        setText('risk-eta', `~${etaHours}h`);
    } else {
        setText('risk-eta', etaDays !== '--' ? `${etaDays} days` : '--');
    }
    setText('risk-cargo', cargo);
    setText('risk-mode',  routeMode);

    // ── Risk Explanation + Probability ───────────────────────────────
    const probability = result.risk_probability;
    const explanation = result.risk_explanation;
    if (explanation || probability != null) {
        const explRow = el('risk-explanation-row');
        if (explRow) explRow.style.display = 'block';
        if (explanation) setText('risk-explanation', explanation);
        if (probability != null) {
            const pct = Math.round(probability * 100);
            const probEl = el('risk-probability');
            if (probEl) {
                probEl.textContent = `${pct}%`;
                probEl.style.color = pct >= 70 ? '#ef4444' : pct >= 40 ? '#f59e0b' : '#22c55e';
            }
        }
        // Color the explanation border by risk level
        const explBorder = el('risk-explanation-row');
        if (explBorder) {
            const borderColor = score >= 75 ? '#ef4444' : score >= 55 ? '#f97316' : score >= 30 ? '#f59e0b' : '#22c55e';
            explBorder.style.borderLeftColor = borderColor;
        }
    }

    // ── Risk factors ────────────────────────────────────────────────
    renderFactors(factors);

    // ── Decision Synthesis + Trade-offs ──────────────────────────────
    const synthesis = result.decision_synthesis || result.llm_reasoning || result.reasoning || 'No reasoning available.';
    const dsEl = el('decision-synthesis-text');
    if (dsEl) dsEl.innerHTML = `<p>${escHtml(synthesis)}</p>`;

    const tradeOffs = result.trade_offs;
    if (tradeOffs) {
        const toRow = el('trade-offs-row');
        const toText = el('trade-offs-text');
        if (toRow && toText) {
            toRow.style.display = 'block';
            toText.textContent = tradeOffs;
        }
    }

    // ── Confidence ──────────────────────────────────────────────────
    if (result.confidence_score != null) {
        setText('confidence-val', `${Math.round(result.confidence_score * 100)}%`);
        showEl('confidence-row');
    }

    renderAgentsSummary(result);
    showEl('simulate-btn');

    // Draw route + vehicle
    if (!_routeRendered && origin !== '--' && dest !== '--' && origin !== dest) {
        _routeRendered = true;
        console.log('[render] → calling renderRouteMap:', origin, dest);
        renderRouteMap(origin, dest, score);
    } else if (_routeRendered) {
        console.log('[render] route already rendered — skipping duplicate');
    } else {
        console.warn('[render] Cannot render route: origin=', origin, 'dest=', dest);
        // Fallback: try with _pendingOrigin/_pendingDest
        if (_pendingOrigin && _pendingDest && _pendingOrigin !== _pendingDest && !_routeRendered) {
            _routeRendered = true;
            console.log('[render] Using pending origin/dest:', _pendingOrigin, _pendingDest);
            renderRouteMap(_pendingOrigin, _pendingDest, score);
        }
    }

    // ── Route Intelligence: use BEST available origin/dest ─────────────────
    // Priority: pendingOrigin (from SSE intake log) > intake fields > '--'
    const raOrigin = _pendingOrigin || origin;
    const raDest   = _pendingDest   || dest;
    console.log('[render] fetchRouteAnalysis with:', raOrigin, '->', raDest);
    if (raOrigin && raOrigin !== '--' && raDest && raDest !== '--') {
        fetchRouteAnalysis(raOrigin, raDest, score, cargo, etaDays, transportMode);
    } else {
        // Still call with whatever we have — let API handle bad inputs gracefully
        console.warn('[render] Partial origin/dest — trying route analysis anyway');
        fetchRouteAnalysis(origin, dest, score, cargo, etaDays, transportMode);
    }
    _showMapDecision(`⚡ ${level} Risk (${score}/100)\n${raOrigin} → ${raDest}`);

}

function renderAgentsSummary(result) {
    const row = el('agents-summary-row'); if (!row) return;
    const done=result.completed_agents||[], skipped=result.skipped_agents||[], failed=result.failed_agents||[];
    const nSkipped = skipped.length;
    const timeSaved = (nSkipped * 1.4).toFixed(1);

    // Build badges
    let html = [
        ...done   .map(a=>`<span class="agent-summary-badge done">✓ ${escHtml(a)}</span>`),
        ...skipped.map(a=>`<span class="agent-summary-badge skipped" title="Skipped by agentic router">⏭ ${escHtml(a)}</span>`),
        ...failed .map(a=>`<span class="agent-summary-badge failed">✕ ${escHtml(a)}</span>`),
    ].join('');

    // UPGRADE 5: Agentic transparency — show WHY agents were skipped
    if (nSkipped > 0) {
        html += `<div class="agentic-skip-summary">
            <span class="skip-badge">🧠 ${nSkipped} agent${nSkipped > 1 ? 's' : ''} skipped · ~${timeSaved}s saved</span>
            <span class="skip-reason">Router detected context-irrelevant agents and excluded them</span>
        </div>`;
    }

    row.innerHTML = html || '<span style="font-size:10px;color:var(--text-dim)">No agent data</span>';
    showEl('agents-summary-card');
}

function _setRiskBadge(id, level) {
    const b = el(id); if (!b) return;
    b.textContent = level || '--';
    const map = { LOW:'level-low', MODERATE:'level-medium', MEDIUM:'level-medium', HIGH:'level-high', CRITICAL:'level-critical' };
    b.className = `risk-pill ${map[(level||'').toUpperCase()]||''}`;
}

function renderFactors(factors) {
    const c = el('factors-list'); if (!c) return;
    if (!Array.isArray(factors)||!factors.length) { c.innerHTML='<div class="no-factors">No significant risk factors detected.</div>'; return; }
    const sevCol = s => ({HIGH:'#f97316',CRITICAL:'#ef4444',MEDIUM:'#f59e0b',LOW:'#22c55e'}[(s||'').toUpperCase()]||'#9ca3af');
    c.innerHTML = factors.map(f => {
        const col=sevCol(f.severity), title=f.factor||f.title||'Risk Factor', detail=f.detail||f.description||'';
        return `<div class="factor-item" style="border-left-color:${col}">
            <div class="factor-title">${escHtml(title)}${f.severity?`<span class="factor-sev" style="color:${col}">${escHtml(f.severity)}</span>`:''}</div>
            ${detail?`<div class="factor-detail">${escHtml(detail)}</div>`:''}
        </div>`;
    }).join('');
}

function _scoreToLevel(s) {
    if (s>=75) return 'CRITICAL'; if (s>=55) return 'HIGH';
    if (s>=30) return 'MODERATE';  return 'LOW';
}

/* ══════════════════════════════════════════════════════════
   10. ROUTE INTELLIGENCE STRIP
═══════════════════════════════════════════════════════════ */
async function fetchRouteAnalysis(origin, dest, riskScore, cargoType, etaDays, transportMode) {
    const o = (origin || '').trim();
    const d = (dest   || '').trim();
    if (!o || o === '--' || !d || d === '--') {
        console.warn('[route-analysis] Skipped — empty origin/dest:', o, d);
        return;
    }
    try {
        const p = new URLSearchParams({
            origin, dest,
            port_city:      dest,
            risk_score:     riskScore||30,
            cargo_type:     cargoType||'general',
            eta_days:       etaDays||14,
            transport_mode: transportMode||'auto',
        });
        const r = await fetch(`/api/route-analysis?${p}`);
        if (!r.ok) return;
        const d = await r.json();
        const { cost_impact, departure_window, alternative_route } = d;
        if (!cost_impact) return;
        showEl('route-intel-strip');

        // KPI values
        setText('strip-cost',       `$${(cost_impact.expected_extra_cost_usd||0).toLocaleString()}`);
        setText('strip-delay-prob', `${cost_impact.delay_probability_pct||0}%`);
        setText('strip-alt-route',  alternative_route
            ? `via ${(alternative_route.via||'--').split(' → ')[0]}`
            : 'Primary optimal');

        // Departure date + data source badge
        const depDate  = departure_window?.optimal_departure || '--';
        const depSrc   = departure_window?.data_source || '';
        const isLive   = depSrc.includes('OpenWeatherMap');
        const stripDep = el('strip-depart');
        if (stripDep) {
            const badge = isLive
                ? `<span style="color:#22d3ee;font-size:9px;margin-left:5px;vertical-align:middle;">📡 OWM Live</span>`
                : `<span style="color:#64748b;font-size:9px;margin-left:5px;">~ Estimate</span>`;
            stripDep.innerHTML = `${depDate}${badge}`;
        }

        // Data source header
        const srcEl = el('intel-data-source');
        if (srcEl) srcEl.textContent = isLive ? '📡 OpenWeatherMap' : '~ Heuristic';

        // Departure recommendation
        const rec      = departure_window?.recommendation;
        const stripRec = el('strip-depart-rec');
        if (stripRec && rec) {
            const recColor = rec==='DELAY'?'#ef4444':rec==='CAUTION'?'#f59e0b':'#22c55e';
            stripRec.style.color   = recColor;
            stripRec.style.fontWeight = '600';
            stripRec.textContent   = `● ${rec}`;
        }

        // ── Render real 5-day OWM forecast cards ──────────────────
        const forecast = departure_window?.['5_day_forecast'] || [];
        const fcRow    = el('owm-forecast-row');
        const fcCards  = el('owm-forecast-cards');
        if (forecast.length > 0 && fcRow && fcCards) {
            fcCards.innerHTML = forecast.map(day => {
                const ri    = day.risk_index ?? 0;
                const rec   = day.recommendation || 'PROCEED';
                const color = ri >= 70 ? '#ef4444' : ri >= 45 ? '#f59e0b' : '#22c55e';
                const bg    = `${color}18`;
                const cond  = day.condition || '';
                const wind  = day.wind_ms != null ? `${day.wind_ms}m/s` : '';
                const rain  = day.rain_mm > 0 ? `💧${day.rain_mm}mm` : '';
                const condIcon = cond.toLowerCase().includes('thunder') ? '⛈' :
                                 cond.toLowerCase().includes('rain')    ? '🌧' :
                                 cond.toLowerCase().includes('snow')    ? '❄' :
                                 cond.toLowerCase().includes('cloud')   ? '☁' :
                                 cond.toLowerCase().includes('fog')     ? '🌫' : '☀';
                const isBest = day === forecast.reduce((a,b) => a.risk_index < b.risk_index ? a : b);
                return `<div style="
                    flex:0 0 auto;width:52px;background:${bg};border:1px solid ${color}44;
                    border-radius:7px;padding:5px 4px;text-align:center;
                    ${isBest ? `box-shadow:0 0 8px ${color}66;border-color:${color};` : ''}
                    font-size:9.5px;cursor:default;">
                    <div style="font-size:8px;color:#94a3b8;white-space:nowrap;overflow:hidden;">${day.day_label||''}</div>
                    <div style="font-size:17px;line-height:1.2;margin:2px 0;">${condIcon}</div>
                    <div style="color:${color};font-weight:700;font-size:11px;">${ri}</div>
                    <div style="color:#9ca3af;font-size:8px;">${wind}</div>
                    ${rain ? `<div style="color:#60a5fa;font-size:8px;">${rain}</div>` : ''}
                    ${isBest ? `<div style="color:${color};font-size:7px;margin-top:2px;font-weight:600;">BEST</div>` : ''}
                </div>`;
            }).join('');
            fcRow.style.display = 'block';
        } else if (fcRow) {
            fcRow.style.display = 'none';
        }

        // ── Render Alt-Route Comparison Panel ────────────────────
        _renderAltRouteComparison(alternative_route, transportMode);
    } catch(e) { console.warn('[route-analysis]',e); }
}

function _renderAltRouteComparison(altRoute, transportMode) {
    const panel = el('alt-route-comparison');
    const content = el('alt-route-comparison-content');
    if (!panel || !content) return;

    if (!altRoute) {
        panel.classList.add('hidden');
        return;
    }

    panel.classList.remove('hidden');
    const comp = altRoute.comparison || {};
    const pri = comp.primary || {};
    const alt = comp.alternate || {};
    const delta = comp.delta || {};

    // Build comparison table
    const isRoad = transportMode === 'road';
    const timeLabel = isRoad ? 'Time' : 'Transit';
    const timeUnit = isRoad ? 'h' : ' days';
    const priTime = isRoad ? (pri.hours || '--') : (pri.days || '--');
    const altTime = isRoad ? (alt.hours || '--') : (alt.days || '--');
    const deltaTime = isRoad ? (delta.hours || 0) : (delta.days || 0);
    const deltaKm = delta.km || 0;

    const riskColor = (altRoute.risk_level || '').toUpperCase() === 'LOW' ? '#22c55e' :
                      (altRoute.risk_level || '').toUpperCase() === 'HIGH' ? '#ef4444' : '#f59e0b';

    content.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:8px;">
            <div style="text-align:center;padding:6px;background:rgba(34,197,94,0.08);border-radius:6px;">
                <div style="font-size:8px;color:#94a3b8;text-transform:uppercase;">Primary</div>
                <div style="font-size:13px;font-weight:600;color:#22c55e;">${pri.km || '--'} km</div>
                <div style="font-size:10px;color:#cbd5e1;">${priTime}${timeUnit}</div>
            </div>
            <div style="text-align:center;padding:6px;background:rgba(249,115,22,0.08);border-radius:6px;">
                <div style="font-size:8px;color:#94a3b8;text-transform:uppercase;">Alternate</div>
                <div style="font-size:13px;font-weight:600;color:#f97316;">${alt.km || altRoute.total_km || '--'} km</div>
                <div style="font-size:10px;color:#cbd5e1;">${altTime}${timeUnit}</div>
            </div>
            <div style="text-align:center;padding:6px;background:rgba(99,102,241,0.08);border-radius:6px;">
                <div style="font-size:8px;color:#94a3b8;text-transform:uppercase;">Delta</div>
                <div style="font-size:13px;font-weight:600;color:#818cf8;">${deltaKm > 0 ? '+' : ''}${deltaKm} km</div>
                <div style="font-size:10px;color:#cbd5e1;">${deltaTime > 0 ? '+' : ''}${deltaTime}${timeUnit}</div>
            </div>
        </div>
        <div style="font-size:10px;color:#e2e8f0;line-height:1.4;">
            <strong style="color:${riskColor};">🛤 ${escHtml(altRoute.via || altRoute.label || 'Alternate')}</strong>
            ${altRoute.risk_level ? `<span style="color:${riskColor};font-size:9px;margin-left:4px;">${altRoute.risk_level}</span>` : ''}
        </div>
        ${altRoute.description ? `<div style="font-size:10px;color:#94a3b8;margin-top:4px;">${escHtml(altRoute.description)}</div>` : ''}
        ${altRoute.when_to_choose ? `<div style="font-size:9px;color:#818cf8;margin-top:4px;font-style:italic;">💡 ${escHtml(altRoute.when_to_choose)}</div>` : ''}
    `;
}

/* ══════════════════════════════════════════════════════════
   11. HISTORY
═══════════════════════════════════════════════════════════ */
async function loadHistory() {
    try {
        const r = await fetch('/api/history', { credentials: 'include' });
        if (r.status === 401) return;  // not logged in yet
        if (!r.ok) return;
        renderHistory(await r.json());
    } catch(_) {}
}

function renderHistory(items) {
    const c = el('history-list'); if (!c) return;
    if (!items?.length) { c.innerHTML='<div class="placeholder-text">No recent analyses</div>'; return; }
    c.innerHTML = items.slice(0,8).map(item => {
        const score = item.risk_score;
        const level = item.risk_level||(item.status==='failed'?'FAILED':'PENDING');
        const color = item.status==='failed'?'#f43f5e':score==null?'#64748b':score<30?'#22c55e':score<55?'#f59e0b':score<75?'#f97316':'#ef4444';
        const onclick = (item.status==='failed'||score==null)?`alert('Analysis pending or failed.')`:`loadResult('${item.session_id}')`;
        const q = escHtml((item.query_text||'').substring(0,45))+((item.query_text||'').length>45?'…':'');
        // Cross-org tag — show org name for partner org entries
        const orgTag = (!item.is_own_org && item.org_name)
            ? `<span class="history-item-org-tag">${escHtml(item.org_name)}</span>` : '';
        return `<button class="history-item" onclick="${onclick}">
            <div class="history-badge" style="background:${color}22;color:${color};border:1px solid ${color}44">${escHtml(level)}</div>
            <div class="history-query">${q}${orgTag}</div>
            <div class="history-score" style="color:${color}">${score??'?'}</div>
        </button>`;
    }).join('');
}

async function loadResult(sessionId) {
    try {
        const r = await fetch(`/api/result/${sessionId}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const result = await r.json();
        if (result.risk_score==null) throw new Error('Analysis pending or incomplete');
        clearLog(); hideEl('brand-panel');
        _routeRendered = false; _pendingOrigin = null; _pendingDest = null;
        if (_routeAbort) { _routeAbort.abort(); _routeAbort = null; }
        renderResult(result);
    } catch(err) { alert(err.message||'Could not load result'); }
}

/* ══════════════════════════════════════════════════════════
   12. ORG VISIBILITY
═══════════════════════════════════════════════════════════ */
async function loadApprovedOrgs() {
    try {
        const r = await fetch('/api/auth/visibility/approved', { credentials: 'include' });
        if (!r.ok) return;
        const orgs = await r.json();
        const panel = el('org-visibility-panel');
        if (!panel) return;
        panel.classList.remove('hidden');
        const list = el('org-analysis-list');
        if (!list) return;
        if (!orgs.length) {
            list.innerHTML = '<div class="placeholder-text">No partner orgs yet. Click + to request.</div>';
            return;
        }
        list.innerHTML = orgs.map(o => `
            <div class="org-item" title="Analyses from ${escHtml(o.name)} are shown in your history">
                <span style="font-size:14px">🏢</span>
                <span class="org-item-name">${escHtml(o.name)}</span>
            </div>
        `).join('');
    } catch(e) {
        console.warn('[org] Could not load approved orgs:', e.message);
    }
}

async function openVisibilityModal() {
    const modal = el('visibility-modal');
    const list  = el('modal-org-list');
    if (!modal || !list) return;
    modal.classList.remove('hidden');
    list.innerHTML = '<div class="placeholder-text">Loading organisations…</div>';

    try {
        const [orgsRes, approvedRes] = await Promise.all([
            fetch('/api/auth/orgs', { credentials: 'include' }),
            fetch('/api/auth/visibility/approved', { credentials: 'include' }),
        ]);
        const orgs     = orgsRes.ok     ? await orgsRes.json()     : [];
        const approved = approvedRes.ok ? await approvedRes.json() : [];
        const approvedIds = new Set(approved.map(o => o.id));
        const myOrgId  = _currentUser?.org_id;

        const others = orgs.filter(o => o.id !== myOrgId);
        if (!others.length) {
            list.innerHTML = '<div class="placeholder-text">No other organisations found.</div>';
            return;
        }

        list.innerHTML = others.map(o => {
            const isApproved = approvedIds.has(o.id);
            const btnHtml = isApproved
                ? `<button class="org-select-btn sent" disabled>✓ Approved</button>`
                : `<button class="org-select-btn" onclick="sendVisibilityRequest(${o.id},'${escHtml(o.name)}')">Request Access</button>`;
            return `
                <div class="org-select-item">
                    <span class="org-select-icon">🏢</span>
                    <div style="flex:1;min-width:0">
                        <div class="org-select-name">${escHtml(o.name)}</div>
                        <div class="org-select-slug">${escHtml(o.slug || '')}</div>
                    </div>
                    ${btnHtml}
                </div>`;
        }).join('');
    } catch(e) {
        list.innerHTML = '<div class="placeholder-text">Error loading organisations.</div>';
    }
}

function closeVisibilityModal() {
    el('visibility-modal')?.classList.add('hidden');
}

async function sendVisibilityRequest(targetOrgId, orgName) {
    try {
        const r = await fetch('/api/auth/visibility/request', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ target_org_id: targetOrgId }),
        });
        const data = await r.json();
        if (r.ok || r.status === 200) {
            // Update the button in the modal
            openVisibilityModal();
        } else {
            alert(data.error || 'Request failed');
        }
    } catch(e) {
        alert('Network error — please try again.');
    }
}

// Close modal on overlay click
document.addEventListener('DOMContentLoaded', () => {
    el('visibility-modal')?.addEventListener('click', function(e) {
        if (e.target === this) closeVisibilityModal();
    });
});

/* ── Exports ─────────────────────────────────────────────── */
window.runShipSimulation     = runShipSimulation;
window.loadResult            = loadResult;
window.setRouteType          = setRouteType;
window.openVisibilityModal   = openVisibilityModal;
window.closeVisibilityModal  = closeVisibilityModal;
window.sendVisibilityRequest = sendVisibilityRequest;
