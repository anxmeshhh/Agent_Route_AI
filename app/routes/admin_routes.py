"""
app/routes/admin_routes.py — Super Admin API endpoints

Blueprint: admin_bp  (registered at /api/admin/...)

All endpoints require @superadmin_required — only role='superadmin' users.

Endpoints:
  GET  /api/admin/stats          — System-wide statistics
  GET  /api/admin/users          — List all users (all orgs)
  POST /api/admin/users          — Create user in any org
  PATCH /api/admin/users/<id>    — Update user (role, active, name)
  DELETE /api/admin/users/<id>   — Soft-delete user
  GET  /api/admin/orgs           — List all orgs with counts
  GET  /api/admin/tickets        — All tickets (all orgs, paginated)
  GET  /api/admin/tickets/<id>   — Full ticket detail + result
  GET  /api/admin/logs           — Agent logs (paginated, filterable)
  GET  /api/admin/logs/system    — Application-level system logs
  GET  /api/admin/health         — System health check
"""
import os
import time
import logging
import psutil
from datetime import datetime

from flask import Blueprint, request, jsonify, g

from ..database import execute_query
from ..auth.decorators import superadmin_required
from ..auth.crypto import hash_password, hash_email, encrypt_email
from ._sse import _sse_queues, _sse_metrics, _safe_json

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__)


# ══════════════════════════════════════════════════════════════
# SYSTEM STATS
# ══════════════════════════════════════════════════════════════

@admin_bp.route("/admin/stats", methods=["GET"])
@superadmin_required
def admin_stats():
    """System-wide dashboard statistics."""
    try:
        users = execute_query("SELECT COUNT(*) AS c FROM users", fetch=True)[0]["c"]
        active_users = execute_query(
            "SELECT COUNT(*) AS c FROM users WHERE is_active=1", fetch=True
        )[0]["c"]
        orgs = execute_query("SELECT COUNT(*) AS c FROM organisations", fetch=True)[0]["c"]

        # Tickets
        tickets_total = 0
        tickets_open = 0
        tickets_completed = 0
        tickets_failed = 0
        try:
            tickets_total = execute_query(
                "SELECT COUNT(*) AS c FROM shipment_tickets", fetch=True
            )[0]["c"]
            tickets_open = execute_query(
                "SELECT COUNT(*) AS c FROM shipment_tickets WHERE status='open'", fetch=True
            )[0]["c"]
            tickets_completed = execute_query(
                "SELECT COUNT(*) AS c FROM shipment_tickets WHERE status='completed'", fetch=True
            )[0]["c"]
            tickets_failed = execute_query(
                "SELECT COUNT(*) AS c FROM shipment_tickets WHERE status='failed'", fetch=True
            )[0]["c"]
        except Exception:
            pass

        # Shipments / analyses
        shipments = execute_query("SELECT COUNT(*) AS c FROM shipments", fetch=True)[0]["c"]
        analyses = 0
        try:
            analyses = execute_query(
                "SELECT COUNT(*) AS c FROM risk_assessments", fetch=True
            )[0]["c"]
        except Exception:
            pass

        # Active SSE sessions
        active_sse = len([m for m in _sse_metrics.values() if not m.get("done")])

        return jsonify({
            "users":            users,
            "active_users":     active_users,
            "organisations":    orgs,
            "tickets_total":    tickets_total,
            "tickets_open":     tickets_open,
            "tickets_completed": tickets_completed,
            "tickets_failed":   tickets_failed,
            "shipments":        shipments,
            "analyses":         analyses,
            "active_sse":       active_sse,
        })
    except Exception as e:
        logger.exception(f"[admin] stats error: {e}")
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ══════════════════════════════════════════════════════════════

@admin_bp.route("/admin/users", methods=["GET"])
@superadmin_required
def list_all_users():
    """List all users across all organisations."""
    rows = execute_query("""
        SELECT u.id, u.display_name, u.role, u.is_active, u.org_id,
               o.name AS org_name, o.slug AS org_slug,
               CAST(u.created_at AS CHAR) AS created_at
        FROM users u
        JOIN organisations o ON o.id = u.org_id
        ORDER BY u.id DESC
    """, fetch=True)
    return jsonify(rows)


@admin_bp.route("/admin/users", methods=["POST"])
@superadmin_required
def create_user():
    """Create a new user in any org. Body: {org_id, display_name, email, password, role}"""
    body = request.get_json(silent=True) or {}
    org_id = body.get("org_id")
    display_name = (body.get("display_name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    role = (body.get("role") or "user").strip().lower()

    if not all([org_id, display_name, email, password]):
        return jsonify({"error": "org_id, display_name, email, password required"}), 400
    if role not in ("user", "member", "admin", "superadmin"):
        role = "user"
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    # Check org exists
    org = execute_query("SELECT id FROM organisations WHERE id=%s", (org_id,), fetch=True)
    if not org:
        return jsonify({"error": "Organisation not found"}), 404

    # Check email uniqueness
    e_hash = hash_email(email)
    existing = execute_query(
        "SELECT id FROM users WHERE email_hash=%s LIMIT 1", (e_hash,), fetch=True
    )
    if existing:
        return jsonify({"error": "Email already registered"}), 409

    e_enc = encrypt_email(email)
    p_hash = hash_password(password)

    user_id = execute_query("""
        INSERT INTO users (org_id, display_name, email_enc, email_hash, password_hash, role, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, 1)
    """, (org_id, display_name, e_enc, e_hash, p_hash, role))

    return jsonify({"message": "User created", "user_id": user_id}), 201


@admin_bp.route("/admin/users/<int:user_id>", methods=["PATCH"])
@superadmin_required
def update_user(user_id):
    """Update user fields. Body: {display_name?, role?, is_active?}"""
    body = request.get_json(silent=True) or {}

    sets = []
    vals = []

    if "display_name" in body:
        sets.append("display_name=%s")
        vals.append(body["display_name"])
    if "role" in body and body["role"] in ("user", "member", "admin", "superadmin"):
        sets.append("role=%s")
        vals.append(body["role"])
    if "is_active" in body:
        sets.append("is_active=%s")
        vals.append(1 if body["is_active"] else 0)
    if "org_id" in body:
        sets.append("org_id=%s")
        vals.append(body["org_id"])

    if not sets:
        return jsonify({"error": "No fields to update"}), 400

    vals.append(user_id)
    execute_query(f"UPDATE users SET {', '.join(sets)} WHERE id=%s", tuple(vals))
    return jsonify({"message": "User updated"})


@admin_bp.route("/admin/users/<int:user_id>", methods=["DELETE"])
@superadmin_required
def delete_user(user_id):
    """Soft-delete user (set is_active=0). Prevents self-deletion."""
    if str(user_id) == str(g.user_id):
        return jsonify({"error": "Cannot deactivate yourself"}), 400

    execute_query("UPDATE users SET is_active=0 WHERE id=%s", (user_id,))
    return jsonify({"message": "User deactivated"})


# ══════════════════════════════════════════════════════════════
# ORGANISATIONS
# ══════════════════════════════════════════════════════════════

@admin_bp.route("/admin/orgs", methods=["GET"])
@superadmin_required
def list_all_orgs():
    """List all organisations with member counts."""
    rows = execute_query("""
        SELECT o.id, o.name, o.slug,
               CAST(o.created_at AS CHAR) AS created_at,
               COUNT(u.id) AS member_count,
               SUM(CASE WHEN u.is_active=1 THEN 1 ELSE 0 END) AS active_members
        FROM organisations o
        LEFT JOIN users u ON u.org_id = o.id
        GROUP BY o.id
        ORDER BY o.id
    """, fetch=True)
    return jsonify(rows)


# ══════════════════════════════════════════════════════════════
# TICKETS (ALL ORGS)
# ══════════════════════════════════════════════════════════════

@admin_bp.route("/admin/tickets", methods=["GET"])
@superadmin_required
def list_all_tickets():
    """List all tickets across all orgs (paginated)."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 50)), 200)
    status = request.args.get("status")
    offset = (page - 1) * per_page

    where = ""
    params = []
    if status:
        where = "WHERE t.status=%s"
        params.append(status)

    # Count
    count_rows = execute_query(
        f"SELECT COUNT(*) AS c FROM shipment_tickets t {where}",
        tuple(params), fetch=True
    )
    total = count_rows[0]["c"] if count_rows else 0

    params.extend([per_page, offset])
    rows = execute_query(f"""
        SELECT t.ticket_id, t.shipment_uuid, t.title, t.transport_mode,
               t.cargo_type, t.origin, t.destination, t.priority, t.status,
               t.org_id, o.name AS org_name,
               CAST(t.created_at AS CHAR) AS created_at,
               CAST(t.updated_at AS CHAR) AS updated_at
        FROM shipment_tickets t
        LEFT JOIN organisations o ON o.id = t.org_id
        {where}
        ORDER BY t.id DESC
        LIMIT %s OFFSET %s
    """, tuple(params), fetch=True)

    return jsonify({
        "tickets": rows,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page else 1,
    })


@admin_bp.route("/admin/tickets/<ticket_id>", methods=["GET"])
@superadmin_required
def get_ticket_detail(ticket_id):
    """Full ticket detail including result_json, threat_json, reroute_json."""
    rows = execute_query("""
        SELECT t.*, o.name AS org_name
        FROM shipment_tickets t
        LEFT JOIN organisations o ON o.id = t.org_id
        WHERE t.ticket_id=%s
    """, (ticket_id,), fetch=True)

    if not rows:
        return jsonify({"error": "Ticket not found"}), 404

    ticket = rows[0]
    # Serialize datetime/Decimal fields
    for k, v in ticket.items():
        if isinstance(v, datetime):
            ticket[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        elif hasattr(v, "__float__"):
            ticket[k] = float(v)

    return jsonify(ticket)


# ══════════════════════════════════════════════════════════════
# AGENT LOGS
# ══════════════════════════════════════════════════════════════

@admin_bp.route("/admin/logs", methods=["GET"])
@superadmin_required
def get_agent_logs():
    """Paginated agent execution logs with filtering."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 100)), 500)
    agent = request.args.get("agent")
    status_filter = request.args.get("status")
    session = request.args.get("session_id")
    offset = (page - 1) * per_page

    where_clauses = []
    params = []

    if agent:
        where_clauses.append("agent_name=%s")
        params.append(agent)
    if status_filter:
        where_clauses.append("status=%s")
        params.append(status_filter)
    if session:
        where_clauses.append("session_id=%s")
        params.append(session)

    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    count_rows = execute_query(
        f"SELECT COUNT(*) AS c FROM agent_logs {where}",
        tuple(params), fetch=True
    )
    total = count_rows[0]["c"] if count_rows else 0

    params.extend([per_page, offset])
    rows = execute_query(f"""
        SELECT id, session_id, agent_name, action, status, message,
               duration_ms, CAST(created_at AS CHAR) AS created_at
        FROM agent_logs {where}
        ORDER BY id DESC
        LIMIT %s OFFSET %s
    """, tuple(params), fetch=True)

    return jsonify({
        "logs": rows,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page else 1,
    })


@admin_bp.route("/admin/logs/system", methods=["GET"])
@superadmin_required
def get_system_logs():
    """Application-level system logs."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 100)), 500)
    level = request.args.get("level")
    offset = (page - 1) * per_page

    where = ""
    params = []
    if level:
        where = "WHERE level=%s"
        params.append(level.upper())

    count_rows = execute_query(
        f"SELECT COUNT(*) AS c FROM system_logs {where}",
        tuple(params), fetch=True
    )
    total = count_rows[0]["c"] if count_rows else 0

    params.extend([per_page, offset])
    rows = execute_query(f"""
        SELECT id, level, module, message,
               CAST(created_at AS CHAR) AS created_at
        FROM system_logs {where}
        ORDER BY id DESC
        LIMIT %s OFFSET %s
    """, tuple(params), fetch=True)

    return jsonify({
        "logs": rows,
        "total": total,
        "page": page,
    })


# ══════════════════════════════════════════════════════════════
# SYSTEM HEALTH
# ══════════════════════════════════════════════════════════════

@admin_bp.route("/admin/health", methods=["GET"])
@superadmin_required
def system_health():
    """Comprehensive system health check."""
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }

    # Database
    try:
        db_rows = execute_query("SELECT 1 AS ok", fetch=True)
        health["components"]["database"] = {
            "status": "up" if db_rows else "down",
            "type": "MySQL",
        }
    except Exception as e:
        health["components"]["database"] = {"status": "down", "error": str(e)}
        health["status"] = "degraded"

    # SSE sessions
    total_sse = len(_sse_queues)
    active_sse = len([m for m in _sse_metrics.values() if not m.get("done")])
    health["components"]["sse"] = {
        "total_sessions": total_sse,
        "active_sessions": active_sse,
    }

    # System resources
    try:
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        health["components"]["system"] = {
            "memory_mb": round(mem.rss / 1024 / 1024, 1),
            "cpu_percent": proc.cpu_percent(interval=0.1),
            "threads": proc.num_threads(),
            "pid": os.getpid(),
            "uptime_seconds": round(time.time() - proc.create_time()),
        }
    except Exception:
        health["components"]["system"] = {"memory_mb": "N/A", "cpu_percent": "N/A"}

    # Table row counts
    try:
        tables = {}
        for tbl in ["users", "organisations", "shipments", "agent_logs", "risk_assessments"]:
            try:
                r = execute_query(f"SELECT COUNT(*) AS c FROM {tbl}", fetch=True)
                tables[tbl] = r[0]["c"]
            except Exception:
                tables[tbl] = "N/A"
        try:
            r = execute_query("SELECT COUNT(*) AS c FROM shipment_tickets", fetch=True)
            tables["shipment_tickets"] = r[0]["c"]
        except Exception:
            tables["shipment_tickets"] = "N/A"
        health["components"]["tables"] = tables
    except Exception:
        pass

    return jsonify(health)
