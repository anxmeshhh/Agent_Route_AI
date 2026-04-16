"""
app/routes/_sse.py — Production-Grade Server-Sent Events Infrastructure

Features:
  - Monotonic event IDs per session (supports Last-Event-ID reconnection)
  - Session metrics (events_pushed, created_at, last_push_at)
  - Bounded key creation (no phantom sessions from random polls)
  - Background cleanup thread (every 60s)
  - Automatic post-done grace period cleanup

Public API:
  _safe_json(obj) -> str
  push_sse_event(session_id, event_type, data)
  pop_sse_events(session_id, after_id=0) -> list[dict]
  mark_session_done(session_id)
  init_sse_session(session_id)
  get_session_metrics(session_id) -> dict | None
"""
import json
import time
import logging
import threading
import decimal
import atexit
from datetime import datetime, date

logger = logging.getLogger(__name__)

# ── JSON serializer ────────────────────────────────────────────────

def _safe_json(obj) -> str:
    """JSON-serialize any object — converts Decimal, datetime, etc. safely."""
    def _default(o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return str(o)
    return json.dumps(obj, default=_default)


# ── In-memory SSE queue ────────────────────────────────────────────
# session_id → list of events (each event has an 'id' field)
_sse_queues: dict[str, list] = {}
_sse_timestamps: dict[str, float] = {}     # session_id → creation time
_sse_counters: dict[str, int] = {}         # session_id → monotonic event counter
_sse_metrics: dict[str, dict] = {}         # session_id → {events_pushed, last_push_at, done}
_sse_lock = threading.Lock()
_SSE_MAX_AGE_S = 600        # Auto-cleanup SSE queues older than 10 minutes
_SSE_DONE_GRACE_S = 30      # Keep done sessions for 30s (allows late reconnect)
_cleanup_thread = None


def _cleanup_stale_sse_queues():
    """Remove SSE queues older than _SSE_MAX_AGE_S, and done sessions past grace period."""
    now = time.time()
    cutoff = now - _SSE_MAX_AGE_S
    stale = []
    for sid, ts in list(_sse_timestamps.items()):
        # Stale by age
        if ts < cutoff:
            stale.append(sid)
            continue
        # Done + grace period expired
        metrics = _sse_metrics.get(sid)
        if metrics and metrics.get("done") and (now - metrics.get("done_at", 0)) > _SSE_DONE_GRACE_S:
            stale.append(sid)
    for sid in stale:
        _sse_queues.pop(sid, None)
        _sse_timestamps.pop(sid, None)
        _sse_counters.pop(sid, None)
        _sse_metrics.pop(sid, None)
    if stale:
        logger.debug(f"[sse] Cleaned up {len(stale)} stale SSE sessions")


def _background_cleanup_loop():
    """Background thread: runs cleanup every 60 seconds."""
    while True:
        time.sleep(60)
        try:
            with _sse_lock:
                _cleanup_stale_sse_queues()
        except Exception as e:
            logger.warning(f"[sse] Cleanup error: {e}")


def _start_cleanup_thread():
    """Start the background cleanup daemon (once)."""
    global _cleanup_thread
    if _cleanup_thread is None or not _cleanup_thread.is_alive():
        _cleanup_thread = threading.Thread(target=_background_cleanup_loop, daemon=True, name="sse-cleanup")
        _cleanup_thread.start()
        logger.debug("[sse] Background cleanup thread started")


# Auto-start cleanup on module import
_start_cleanup_thread()


def push_sse_event(session_id: str, event_type: str, data: dict):
    """Thread-safe push to SSE queue with monotonic event ID."""
    with _sse_lock:
        if session_id not in _sse_queues:
            # Session must be initialized first — auto-init as safety net
            _sse_queues[session_id] = []
            _sse_timestamps[session_id] = time.time()
            _sse_counters[session_id] = 0
            _sse_metrics[session_id] = {"events_pushed": 0, "created_at": time.time(), "last_push_at": 0, "done": False}

        _sse_counters[session_id] += 1
        event_id = _sse_counters[session_id]

        _sse_queues[session_id].append({
            "id": event_id,
            "type": event_type,
            "data": data,
            "ts": datetime.utcnow().isoformat(),
        })

        # Update metrics
        metrics = _sse_metrics.get(session_id, {})
        metrics["events_pushed"] = metrics.get("events_pushed", 0) + 1
        metrics["last_push_at"] = time.time()
        _sse_metrics[session_id] = metrics


def pop_sse_events(session_id: str, after_id: int = 0) -> list:
    """
    Pop events for a session. If after_id > 0, return only events with id > after_id
    (supports Last-Event-ID reconnection).

    Does NOT create keys for unknown sessions — prevents memory leak from random polls.
    """
    with _sse_lock:
        if session_id not in _sse_queues:
            return []  # Unknown session — don't create phantom keys

        events = _sse_queues.get(session_id, [])
        if after_id > 0:
            events = [e for e in events if e.get("id", 0) > after_id]
        else:
            events = events.copy()

        # Clear consumed events
        _sse_queues[session_id] = []
        return events


def mark_session_done(session_id: str):
    """Mark session as complete — inject done event, schedule cleanup."""
    with _sse_lock:
        _sse_queues.setdefault(session_id, [])
        _sse_counters.setdefault(session_id, 0)
        _sse_counters[session_id] += 1
        event_id = _sse_counters[session_id]

        _sse_queues[session_id].append({
            "id": event_id,
            "type": "done",
            "data": {},
            "ts": datetime.utcnow().isoformat(),
        })

        # Mark done in metrics
        metrics = _sse_metrics.get(session_id, {})
        metrics["done"] = True
        metrics["done_at"] = time.time()
        _sse_metrics[session_id] = metrics


def init_sse_session(session_id: str):
    """Pre-create an empty SSE queue for a session before the pipeline thread starts."""
    with _sse_lock:
        _sse_queues[session_id] = []
        _sse_timestamps[session_id] = time.time()
        _sse_counters[session_id] = 0
        _sse_metrics[session_id] = {
            "events_pushed": 0,
            "created_at": time.time(),
            "last_push_at": 0,
            "done": False,
        }


def get_session_metrics(session_id: str) -> dict:
    """Return observability metrics for a session (or None if unknown)."""
    with _sse_lock:
        return _sse_metrics.get(session_id)
