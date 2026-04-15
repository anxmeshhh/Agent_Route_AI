"""
app/routes/stream_routes.py — GET /stream/<session_id> (SSE)

Production-grade SSE with:
  - Monotonic event IDs (id: field)
  - retry: hint for auto-reconnect
  - Last-Event-ID header support for resumption
  - Reduced heartbeat interval (250ms)

Blueprint: stream_bp
"""
import time
import logging

from flask import Blueprint, Response, request, stream_with_context

from ._sse import pop_sse_events, _safe_json

logger = logging.getLogger(__name__)
stream_bp = Blueprint("stream", __name__)


@stream_bp.route("/stream/<session_id>")
def stream(session_id):
    """Server-Sent Events endpoint for live agent reasoning."""
    # Support Last-Event-ID reconnection
    last_event_id = request.headers.get("Last-Event-ID", "0")
    try:
        last_event_id = int(last_event_id)
    except (ValueError, TypeError):
        last_event_id = 0

    def generate():
        timeout = 180  # 3 minutes max
        start = time.time()
        done = False
        after_id = last_event_id

        # Send retry hint on first connect (3 seconds)
        yield "retry: 3000\n\n"

        while not done and (time.time() - start) < timeout:
            events = pop_sse_events(session_id, after_id=after_id)
            for event in events:
                event_id = event.get("id", 0)
                if event_id > after_id:
                    after_id = event_id

                if event["type"] == "done":
                    done = True
                    yield f"id: {event_id}\nevent: done\ndata: {{}}\n\n"
                    break
                try:
                    payload = _safe_json(event)
                except Exception as e:
                    logger.warning(f"[sse] Serialization error: {e}")
                    continue
                yield f"id: {event_id}\nevent: {event['type']}\ndata: {payload}\n\n"

            if not done:
                yield ": heartbeat\n\n"
                time.sleep(0.25)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
