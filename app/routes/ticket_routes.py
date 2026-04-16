"""
app/routes/ticket_routes.py  —  Shipment Ticket System
execute_query(query, params, fetch=True) returns list of dicts (dictionary cursor).
fetch=False (default) commits and returns lastrowid.
"""
import uuid, json, threading, logging
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app, g
from ..database import execute_query
from ..auth.decorators import login_required
from ._sse import init_sse_session, push_sse_event, mark_session_done
from ._db_helpers import _store_shipment, _update_shipment_status, _log_to_db

logger = logging.getLogger(__name__)
ticket_bp = Blueprint("tickets", __name__)

_VALID_PRIORITY = {"low", "medium", "high", "critical"}
_VALID_STATUS   = {"open", "in_progress", "completed", "failed", "closed"}
_VALID_MODE     = {"road", "sea", "air"}

_SELECT_COLS = (
    "ticket_id, shipment_uuid, title, transport_mode, cargo_type, "
    "weight_kg, budget_usd, eta_days, origin, destination, priority, status, "
    "session_id, CAST(created_at AS CHAR) AS created_at, "
    "result_json, threat_json, reroute_json"
)


def _next_ticket_id() -> str:
    """Atomically increment ticket_sequence and return TKT-XXXXX."""
    execute_query("UPDATE ticket_sequence SET next_val = LAST_INSERT_ID(next_val + 1)")
    rows = execute_query("SELECT LAST_INSERT_ID() AS n", fetch=True)
    n = rows[0]["n"] if rows else 1
    return f"TKT-{int(n):05d}"


def _serialize(row: dict) -> dict:
    """Convert a dict row to JSON-safe types."""
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        elif hasattr(v, "__float__"):
            out[k] = float(v)
        else:
            out[k] = v
    return out


# ── CREATE TICKET ────────────────────────────────────────────────────
@ticket_bp.route("/tickets", methods=["POST"])
@login_required
def create_ticket():
    b = request.get_json(silent=True) or {}
    org_id  = getattr(g, "org_id",  1)
    user_id = getattr(g, "user_id", None)

    shipment_uuid  = (b.get("shipment_uuid")  or "").strip()
    origin         = (b.get("origin")         or "").strip()
    destination    = (b.get("destination")    or "").strip()
    cargo_type     = (b.get("cargo_type")     or "general").strip().lower()
    transport_mode = (b.get("transport_mode") or "road").strip().lower()
    priority       = (b.get("priority")       or "medium").strip().lower()
    title          = (b.get("title")          or "").strip()
    weight_kg      = b.get("weight_kg")
    budget_usd     = b.get("budget_usd")
    eta_days       = b.get("eta_days")

    if not shipment_uuid or not origin or not destination:
        return jsonify({"error": "shipment_uuid, origin and destination are required"}), 400

    if transport_mode not in _VALID_MODE:     transport_mode = "road"
    if priority       not in _VALID_PRIORITY: priority       = "medium"

    if not title:
        emoji = {"road": "🚗", "sea": "🚢", "air": "✈"}.get(transport_mode, "📦")
        title = f"{emoji} {origin} → {destination} ({cargo_type.title()})"

    ticket_id = _next_ticket_id()

    execute_query(
        """INSERT INTO shipment_tickets
           (ticket_id, shipment_uuid, org_id, user_id, title,
            transport_mode, cargo_type, weight_kg, budget_usd, eta_days,
            origin, destination, priority, status)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'open')""",
        (ticket_id, shipment_uuid, org_id, user_id, title,
         transport_mode, cargo_type,
         float(weight_kg)  if weight_kg  else None,
         float(budget_usd) if budget_usd else None,
         int(eta_days)     if eta_days   else None,
         origin, destination, priority),
    )

    rows = execute_query(
        f"SELECT {_SELECT_COLS} FROM shipment_tickets WHERE ticket_id=%s",
        (ticket_id,), fetch=True
    )
    ticket = _serialize(rows[0]) if rows else {"ticket_id": ticket_id}
    return jsonify({"ticket": ticket}), 201


# ── LIST TICKETS ──────────────────────────────────────────────────
@ticket_bp.route("/tickets", methods=["GET"])
@login_required
def list_tickets():
    org_id        = getattr(g, "org_id", 1)
    shipment_uuid = request.args.get("shipment_uuid", "").strip()
    status_filter = request.args.get("status", "").strip().lower()

    sql  = f"SELECT {_SELECT_COLS} FROM shipment_tickets WHERE org_id=%s"
    args = [org_id]
    if shipment_uuid:
        sql += " AND shipment_uuid=%s"; args.append(shipment_uuid)
    if status_filter and status_filter in _VALID_STATUS:
        sql += " AND status=%s"; args.append(status_filter)
    sql += " ORDER BY created_at DESC LIMIT 100"

    rows = execute_query(sql, tuple(args), fetch=True) or []
    return jsonify({"tickets": [_serialize(r) for r in rows]})


# ── GET SINGLE TICKET ─────────────────────────────────────────────
@ticket_bp.route("/tickets/<ticket_id>", methods=["GET"])
@login_required
def get_ticket(ticket_id):
    org_id = getattr(g, "org_id", 1)
    rows = execute_query(
        f"SELECT {_SELECT_COLS} "
        "FROM shipment_tickets WHERE ticket_id=%s AND org_id=%s",
        (ticket_id, org_id), fetch=True
    )
    if not rows:
        return jsonify({"error": "Ticket not found"}), 404
    d = _serialize(rows[0])
    # Parse cached JSON columns
    for col, key in [("result_json", "result"), ("threat_json", "threat"), ("reroute_json", "reroutes")]:
        raw = rows[0].get(col)
        if raw:
            try:
                d[key] = json.loads(raw) if isinstance(raw, str) else raw
            except: pass
    return jsonify({"ticket": d})


# ── TRIGGER ANALYSIS ──────────────────────────────────────────────
@ticket_bp.route("/tickets/<ticket_id>/analyze", methods=["POST"])
@login_required
def analyze_ticket(ticket_id):
    org_id  = getattr(g, "org_id",  1)
    user_id = getattr(g, "user_id", None)

    rows = execute_query(
        f"SELECT {_SELECT_COLS} FROM shipment_tickets WHERE ticket_id=%s AND org_id=%s",
        (ticket_id, org_id), fetch=True
    )
    if not rows:
        return jsonify({"error": "Ticket not found"}), 404
    ticket = _serialize(rows[0])

    if ticket["status"] == "in_progress":
        return jsonify({"error": "Analysis already running for this ticket"}), 409

    session_id = str(uuid.uuid4())
    init_sse_session(session_id)

    execute_query(
        "UPDATE shipment_tickets SET session_id=%s, status='in_progress' WHERE ticket_id=%s",
        (session_id, ticket_id)
    )

    app = current_app._get_current_object()
    threading.Thread(
        target=_run_ticket_pipeline,
        args=(app, session_id, ticket, org_id, user_id, ticket_id),
        daemon=True
    ).start()

    return jsonify({
        "session_id":  session_id,
        "ticket_id":   ticket_id,
        "stream_url":  f"/api/stream/{session_id}",
        "status":      "running",
    })


# ── UPDATE STATUS / PRIORITY ──────────────────────────────────────
@ticket_bp.route("/tickets/<ticket_id>/status", methods=["PATCH"])
@login_required
def update_ticket(ticket_id):
    org_id = getattr(g, "org_id", 1)
    b = request.get_json(silent=True) or {}
    new_status   = (b.get("status")   or "").strip().lower()
    new_priority = (b.get("priority") or "").strip().lower()
    sets, args = [], []
    if new_status   in _VALID_STATUS:   sets.append("status=%s");   args.append(new_status)
    if new_priority in _VALID_PRIORITY: sets.append("priority=%s"); args.append(new_priority)
    if not sets:
        return jsonify({"error": "Provide valid status or priority"}), 400
    args += [ticket_id, org_id]
    execute_query(
        f"UPDATE shipment_tickets SET {', '.join(sets)} WHERE ticket_id=%s AND org_id=%s",
        tuple(args)
    )
    return jsonify({"ok": True})


# ── INDUCE THREAT ─────────────────────────────────────────────────
_precaution_agent = None

def _get_precaution():
    global _precaution_agent
    if _precaution_agent is None:
        from ..agents.precaution_agent import PrecautionAgent
        _precaution_agent = PrecautionAgent(current_app.config)
    return _precaution_agent


@ticket_bp.route("/tickets/<ticket_id>/threat", methods=["POST"])
@login_required
def induce_threat(ticket_id):
    """Induce a random realistic mid-route threat via Groq."""
    org_id = getattr(g, "org_id", 1)
    rows = execute_query(
        f"SELECT {_SELECT_COLS} FROM shipment_tickets WHERE ticket_id=%s AND org_id=%s",
        (ticket_id, org_id), fetch=True
    )
    if not rows:
        return jsonify({"error": "Ticket not found"}), 404
    ticket = _serialize(rows[0])

    pa = _get_precaution()
    result = pa.induce_threat(
        ticket["origin"], ticket["destination"],
        ticket["cargo_type"], ticket_id
    )
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Threat gen failed")}), 500

    # Store threat in dedicated column
    execute_query(
        "UPDATE shipment_tickets SET threat_json=%s WHERE ticket_id=%s",
        (json.dumps(result["threat"]), ticket_id)
    )
    return jsonify(result)


@ticket_bp.route("/tickets/<ticket_id>/reroute", methods=["POST"])
@login_required
def reroute_ticket(ticket_id):
    """Generate alternative routes given an active threat."""
    org_id = getattr(g, "org_id", 1)
    b = request.get_json(silent=True) or {}

    rows = execute_query(
        f"SELECT {_SELECT_COLS} FROM shipment_tickets WHERE ticket_id=%s AND org_id=%s",
        (ticket_id, org_id), fetch=True
    )
    if not rows:
        return jsonify({"error": "Ticket not found"}), 404
    ticket = _serialize(rows[0])

    threat = b.get("threat")  # pass from front-end
    pa = _get_precaution()
    result = pa.get_reroutes(
        ticket["origin"], ticket["destination"],
        ticket["cargo_type"], ticket_id, threat
    )
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Reroute gen failed")}), 500

    # Store reroutes in dedicated column
    execute_query(
        "UPDATE shipment_tickets SET reroute_json=%s WHERE ticket_id=%s",
        (json.dumps(result), ticket_id)
    )
    return jsonify(result)


# ── PIPELINE ──────────────────────────────────────────────────────
def _run_ticket_pipeline(app, session_id, ticket, org_id, user_id, ticket_id):
    with app.app_context():
        try:
            from ..agents.intake_agent import IntakeAgent
            from ..agents.graph import AgentGraph

            structured = {
                "origin_port":   ticket["origin"],
                "port":          ticket["destination"],
                "port_city":     ticket["destination"],
                "cargo_type":    ticket["cargo_type"],
                "eta_days":      ticket["eta_days"],
                "shipment_uuid": ticket["shipment_uuid"],
                "budget_usd":    ticket.get("budget_usd"),
                "weight_kg":     ticket.get("weight_kg"),
            }
            mode = ticket.get("transport_mode", "road")
            query_text = (f"{ticket['cargo_type']} cargo from {ticket['origin']} "
                          f"to {ticket['destination']} via {mode}")
            if ticket.get("eta_days"):
                query_text += f" in {ticket['eta_days']} days"

            push_sse_event(session_id, "agent_log", {
                "agent":  "intake",
                "status": "started",
                "action": f"🎫 Ticket {ticket_id} — {ticket['title']}",
            })

            intake = IntakeAgent()
            intake_result = intake.run(query_text, session_id, structured_override=structured)

            for log in intake_result.get("logs", []):
                push_sse_event(session_id, "agent_log", log)

            shipment_id = _store_shipment(session_id, intake_result, org_id, user_id)
            _log_to_db(session_id, "intake", "Shipment stored", "success", {"shipment_id": shipment_id})

            push_sse_event(session_id, "agent_log", {
                "agent":  "graph",
                "status": "started",
                "action": "🧠 Agentic Graph — LLM Router deciding agent sequence...",
            })

            graph = AgentGraph(
                session_id=session_id,
                push_event=push_sse_event,
                config=app.config,
                db_execute=execute_query,
            )
            result = graph.run(query_text, intake_result, shipment_id)

            execute_query(
                "UPDATE shipment_tickets SET status='completed', result_json=%s WHERE ticket_id=%s",
                (json.dumps(result), ticket_id)
            )
            _update_shipment_status(session_id, "completed")
            push_sse_event(session_id, "result", result)
            mark_session_done(session_id)

        except Exception as e:
            logger.exception(f"[ticket] Pipeline error [{ticket_id}]: {e}")
            execute_query(
                "UPDATE shipment_tickets SET status='failed' WHERE ticket_id=%s", (ticket_id,)
            )
            _update_shipment_status(session_id, "failed")
            push_sse_event(session_id, "error", {"message": str(e)})
            mark_session_done(session_id)
