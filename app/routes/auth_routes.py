"""
app/routes/auth_routes.py — All authentication & organisation API endpoints

Blueprint: auth_bp  (registered at /api/auth/...)

Endpoints:
  POST /api/auth/signup              — register org + first admin user
  POST /api/auth/login               — verify password (→ send OTP if enabled)
  POST /api/auth/verify-otp          — validate OTP → issue access + refresh tokens
  POST /api/auth/refresh             — renew access token using refresh cookie
  POST /api/auth/logout              — revoke refresh token + clear cookies
  GET  /api/auth/me                  — current user info (NO PII in response)

  GET  /api/auth/orgs                — list all orgs (for visibility requests)
  GET  /api/auth/org/members         — members of current user's org (admin only)

  POST /api/auth/visibility/request  — request to see another org's analyses
  GET  /api/auth/visibility/requests — pending requests targeting my org (admin)
  POST /api/auth/visibility/respond  — approve / reject a request (admin)
  GET  /api/auth/visibility/approved — orgs whose analyses I can see
"""
import re
import random
import string
import hashlib
import logging
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Blueprint, request, jsonify, make_response, current_app, g

from ..database import execute_query
from ..auth.crypto import (
    encrypt_email, decrypt_email, hash_email,
    hash_password, verify_password,
    generate_access_token, generate_refresh_token, verify_access_token,
)
from ..auth.decorators import login_required, admin_required

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


# ══════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════

def _slugify(name: str) -> str:
    """Convert org name to URL-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug[:64]


def _make_otp() -> str:
    return "".join(random.choices(string.digits, k=6))


def _send_otp_email(to_email: str, otp: str, display_name: str):
    """Send OTP via SMTP. Swallows errors (logs warning)."""
    cfg = current_app.config
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"AgentRoute AI — Your login code: {otp}"
        msg["From"] = cfg.get("SMTP_FROM", "AgentRoute AI")
        msg["To"] = to_email

        html = f"""
        <div style="font-family:sans-serif;background:#0d1117;color:#e2e8f0;padding:32px;border-radius:12px;max-width:480px;margin:auto">
          <h2 style="color:#22c55e;margin-bottom:8px">AgentRoute<span style="color:#818cf8">AI</span></h2>
          <p>Hi <strong>{display_name}</strong>,</p>
          <p>Your one-time login code is:</p>
          <div style="font-size:40px;font-weight:700;letter-spacing:12px;color:#facc15;text-align:center;padding:16px;background:#1e2433;border-radius:8px;margin:16px 0">{otp}</div>
          <p style="color:#94a3b8;font-size:13px">This code expires in 5 minutes. Do not share it with anyone.</p>
          <hr style="border-color:#2d3748;margin:24px 0">
          <p style="font-size:11px;color:#64748b">AgentRoute AI — Shipment Intelligence Platform</p>
        </div>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(cfg.get("SMTP_HOST", "smtp.gmail.com"),
                          int(cfg.get("SMTP_PORT", 587))) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg.get("SMTP_USER", ""), cfg.get("SMTP_PASS", ""))
            server.sendmail(cfg.get("SMTP_USER", ""), to_email, msg.as_string())
    except Exception as e:
        logger.warning(f"OTP email send failed: {e}")


def _set_auth_cookies(response, access_token: str, refresh_token: str):
    """Set HttpOnly cookies — tokens never exposed to JavaScript."""
    cfg = current_app.config
    access_ttl = int(cfg.get("JWT_ACCESS_TTL_MINUTES", 15)) * 60
    refresh_ttl = int(cfg.get("JWT_REFRESH_TTL_DAYS", 7)) * 86400
    secure = not cfg.get("DEBUG", True)  # Secure flag in production

    response.set_cookie(
        "access_token", access_token,
        max_age=access_ttl, httponly=True, secure=secure, samesite="Lax", path="/"
    )
    response.set_cookie(
        "refresh_token", refresh_token,
        max_age=refresh_ttl, httponly=True, secure=secure, samesite="Lax", path="/"
    )


def _clear_auth_cookies(response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


# ══════════════════════════════════════════════════════════════
# SIGNUP
# ══════════════════════════════════════════════════════════════

@auth_bp.route("/auth/signup", methods=["POST"])
def signup():
    """
    Register a new organisation + first admin user.
    Body: { org_name, display_name, email, password }
    """
    body = request.get_json(silent=True) or {}
    org_name = (body.get("org_name") or "").strip()
    display_name = (body.get("display_name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    # ── Validation ────────────────────────────────────────────
    errors = {}
    if not org_name or len(org_name) < 2:
        errors["org_name"] = "Organisation name must be at least 2 characters"
    if not display_name or len(display_name) < 2:
        errors["display_name"] = "Display name must be at least 2 characters"
    if not email or "@" not in email:
        errors["email"] = "Valid email address required"
    if not password or len(password) < 8:
        errors["password"] = "Password must be at least 8 characters"
    if errors:
        return jsonify({"errors": errors}), 400

    slug = _slugify(org_name)

    # Check org name uniqueness
    existing_org = execute_query(
        "SELECT id FROM organisations WHERE name=%s OR slug=%s LIMIT 1",
        (org_name, slug), fetch=True
    )
    if existing_org:
        return jsonify({"errors": {"org_name": "Organisation name already taken"}}), 409

    # Check email uniqueness (via hash)
    e_hash = hash_email(email)
    existing_user = execute_query(
        "SELECT id FROM users WHERE email_hash=%s LIMIT 1",
        (e_hash,), fetch=True
    )
    if existing_user:
        return jsonify({"errors": {"email": "Email already registered"}}), 409

    # ── Create org ────────────────────────────────────────────
    org_id = execute_query(
        "INSERT INTO organisations (name, slug) VALUES (%s, %s)",
        (org_name, slug)
    )

    # ── Create admin user ─────────────────────────────────────
    e_enc = encrypt_email(email)
    p_hash = hash_password(password)

    user_id = execute_query(
        """INSERT INTO users (org_id, display_name, email_enc, email_hash, password_hash, role)
           VALUES (%s, %s, %s, %s, %s, 'admin')""",
        (org_id, display_name, e_enc, e_hash, p_hash)
    )

    # ── Issue tokens immediately (no OTP on first signup) ─────
    access_token = generate_access_token(user_id, org_id, "admin")
    raw_refresh, refresh_hash = generate_refresh_token()

    cfg = current_app.config
    refresh_ttl_days = int(cfg.get("JWT_REFRESH_TTL_DAYS", 7))
    expires_at = datetime.now(timezone.utc) + timedelta(days=refresh_ttl_days)

    execute_query(
        "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
        (user_id, refresh_hash, expires_at.strftime("%Y-%m-%d %H:%M:%S"))
    )

    resp = make_response(jsonify({
        "message": "Organisation created successfully",
        "user": {
            "id": user_id,
            "display_name": display_name,
            "role": "admin",
            "org_id": org_id,
            "org_name": org_name,
            "org_slug": slug,
        }
    }), 201)
    _set_auth_cookies(resp, access_token, raw_refresh)
    return resp


# ══════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════

@auth_bp.route("/auth/login", methods=["POST"])
def login():
    """
    Verify email + password.
    If OTP_ENABLED=true → store OTP, return { otp_required: true }.
    If OTP_ENABLED=false → issue tokens directly.
    Body: { email, password }
    """
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    e_hash = hash_email(email)
    rows = execute_query(
        """SELECT u.id, u.org_id, u.display_name, u.password_hash, u.role, u.is_active,
                  o.name AS org_name, o.slug AS org_slug
           FROM users u
           JOIN organisations o ON o.id = u.org_id
           WHERE u.email_hash=%s LIMIT 1""",
        (e_hash,), fetch=True
    )

    if not rows or not verify_password(password, rows[0]["password_hash"]):
        return jsonify({"error": "Invalid email or password"}), 401

    user = rows[0]
    if not user["is_active"]:
        return jsonify({"error": "Account is inactive. Contact your admin."}), 403

    otp_enabled = current_app.config.get("OTP_ENABLED", False)

    if otp_enabled:
        # Generate and store OTP
        otp = _make_otp()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        execute_query(
            "INSERT INTO mfa_otp (user_id, otp_code, expires_at) VALUES (%s, %s, %s)",
            (user["id"], otp, expires_at.strftime("%Y-%m-%d %H:%M:%S"))
        )
        # Try to send email (decrypting PII only server-side)
        try:
            plain_email = decrypt_email(
                execute_query("SELECT email_enc FROM users WHERE id=%s LIMIT 1",
                              (user["id"],), fetch=True)[0]["email_enc"]
            )
            _send_otp_email(plain_email, otp, user["display_name"])
        except Exception as e:
            logger.warning(f"OTP email attempt failed: {e}")

        return jsonify({
            "otp_required": True,
            "user_id": user["id"],
            "message": "OTP sent to your registered email"
        }), 200

    # OTP disabled — issue tokens directly
    return _issue_tokens_response(user)


# ══════════════════════════════════════════════════════════════
# VERIFY OTP
# ══════════════════════════════════════════════════════════════

@auth_bp.route("/auth/verify-otp", methods=["POST"])
def verify_otp():
    """
    Validate OTP code → issue access + refresh tokens.
    Body: { user_id, otp_code }
    """
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    otp_code = (body.get("otp_code") or "").strip()

    if not user_id or not otp_code:
        return jsonify({"error": "user_id and otp_code required"}), 400

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows = execute_query(
        """SELECT id FROM mfa_otp
           WHERE user_id=%s AND otp_code=%s AND used=0 AND expires_at > %s
           ORDER BY created_at DESC LIMIT 1""",
        (user_id, otp_code, now), fetch=True
    )

    if not rows:
        return jsonify({"error": "Invalid or expired OTP"}), 401

    # Mark OTP used
    execute_query("UPDATE mfa_otp SET used=1 WHERE id=%s", (rows[0]["id"],))

    # Fetch user
    user_rows = execute_query(
        """SELECT u.id, u.org_id, u.display_name, u.role,
                  o.name AS org_name, o.slug AS org_slug
           FROM users u JOIN organisations o ON o.id = u.org_id
           WHERE u.id=%s LIMIT 1""",
        (user_id,), fetch=True
    )
    if not user_rows:
        return jsonify({"error": "User not found"}), 404

    return _issue_tokens_response(user_rows[0])


def _issue_tokens_response(user: dict):
    """Create access + refresh tokens and set cookies."""
    access_token = generate_access_token(user["id"], user["org_id"], user["role"])
    raw_refresh, refresh_hash = generate_refresh_token()

    cfg = current_app.config
    refresh_ttl_days = int(cfg.get("JWT_REFRESH_TTL_DAYS", 7))
    expires_at = datetime.now(timezone.utc) + timedelta(days=refresh_ttl_days)

    execute_query(
        "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
        (user["id"], refresh_hash, expires_at.strftime("%Y-%m-%d %H:%M:%S"))
    )

    resp = make_response(jsonify({
        "message": "Logged in",
        "user": {
            "id": user["id"],
            "display_name": user["display_name"],
            "role": user["role"],
            "org_id": user["org_id"],
            "org_name": user["org_name"],
            "org_slug": user["org_slug"],
        }
    }), 200)
    _set_auth_cookies(resp, access_token, raw_refresh)
    return resp


# ══════════════════════════════════════════════════════════════
# REFRESH TOKEN
# ══════════════════════════════════════════════════════════════

@auth_bp.route("/auth/refresh", methods=["POST"])
def refresh():
    """
    Renew access token using refresh cookie.
    Implements refresh-token rotation.
    """
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        return jsonify({"error": "No refresh token"}), 401

    token_hash = hashlib.sha256(raw_refresh.encode()).hexdigest()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    rows = execute_query(
        """SELECT rt.id, rt.user_id
           FROM refresh_tokens rt
           WHERE rt.token_hash=%s AND rt.revoked=0 AND rt.expires_at > %s
           LIMIT 1""",
        (token_hash, now), fetch=True
    )
    if not rows:
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    rt_id = rows[0]["id"]
    user_id = rows[0]["user_id"]

    # Revoke old refresh token (rotation)
    execute_query("UPDATE refresh_tokens SET revoked=1 WHERE id=%s", (rt_id,))

    # Fetch user
    user_rows = execute_query(
        """SELECT u.id, u.org_id, u.role, u.display_name,
                  o.name AS org_name, o.slug AS org_slug
           FROM users u JOIN organisations o ON o.id = u.org_id
           WHERE u.id=%s AND u.is_active=1 LIMIT 1""",
        (user_id,), fetch=True
    )
    if not user_rows:
        return jsonify({"error": "User not found"}), 404

    return _issue_tokens_response(user_rows[0])


# ══════════════════════════════════════════════════════════════
# LOGOUT
# ══════════════════════════════════════════════════════════════

@auth_bp.route("/auth/logout", methods=["POST"])
def logout():
    """Revoke refresh token + clear cookies."""
    raw_refresh = request.cookies.get("refresh_token")
    if raw_refresh:
        token_hash = hashlib.sha256(raw_refresh.encode()).hexdigest()
        try:
            execute_query(
                "UPDATE refresh_tokens SET revoked=1 WHERE token_hash=%s",
                (token_hash,)
            )
        except Exception:
            pass

    resp = make_response(jsonify({"message": "Logged out"}), 200)
    _clear_auth_cookies(resp)
    return resp


# ══════════════════════════════════════════════════════════════
# ME — Current User (NO PII)
# ══════════════════════════════════════════════════════════════

@auth_bp.route("/auth/me", methods=["GET"])
@login_required
def me():
    """Return current user's non-PII identity info."""
    rows = execute_query(
        """SELECT u.id, u.display_name, u.role, u.org_id,
                  o.name AS org_name, o.slug AS org_slug
           FROM users u JOIN organisations o ON o.id = u.org_id
           WHERE u.id=%s LIMIT 1""",
        (g.user_id,), fetch=True
    )
    if not rows:
        return jsonify({"error": "User not found"}), 404
    return jsonify(rows[0])


# ══════════════════════════════════════════════════════════════
# ORGANISATIONS
# ══════════════════════════════════════════════════════════════

@auth_bp.route("/auth/orgs", methods=["GET"])
@login_required
def list_orgs():
    """List all organisations (for the visibility request flow)."""
    orgs = execute_query(
        "SELECT id, name, slug FROM organisations ORDER BY name ASC",
        fetch=True
    )
    return jsonify(orgs)


@auth_bp.route("/auth/org/members", methods=["GET"])
@login_required
def org_members():
    """List members of the current user's org (admin only sees all, members see self)."""
    if g.role == "admin":
        rows = execute_query(
            """SELECT id, display_name, role, is_active, created_at
               FROM users WHERE org_id=%s ORDER BY role, display_name""",
            (g.org_id,), fetch=True
        )
    else:
        rows = execute_query(
            "SELECT id, display_name, role, is_active, created_at FROM users WHERE id=%s",
            (g.user_id,), fetch=True
        )
    for r in rows:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
    return jsonify(rows)


# ══════════════════════════════════════════════════════════════
# ORG VISIBILITY REQUESTS
# ══════════════════════════════════════════════════════════════

@auth_bp.route("/auth/visibility/request", methods=["POST"])
@login_required
def visibility_request():
    """
    Request to see another org's analyses.
    Body: { target_org_id }
    """
    body = request.get_json(silent=True) or {}
    target_org_id = body.get("target_org_id")

    if not target_org_id:
        return jsonify({"error": "target_org_id required"}), 400
    if int(target_org_id) == g.org_id:
        return jsonify({"error": "Cannot request visibility for your own org"}), 400

    # Check target org exists
    target = execute_query("SELECT id, name FROM organisations WHERE id=%s LIMIT 1",
                           (target_org_id,), fetch=True)
    if not target:
        return jsonify({"error": "Target organisation not found"}), 404

    # Check for existing request
    existing = execute_query(
        "SELECT id, status FROM org_visibility_requests WHERE requester_org_id=%s AND target_org_id=%s LIMIT 1",
        (g.org_id, target_org_id), fetch=True
    )
    if existing:
        return jsonify({
            "message": f"Request already exists (status: {existing[0]['status']})",
            "status": existing[0]["status"]
        }), 200

    execute_query(
        "INSERT INTO org_visibility_requests (requester_org_id, target_org_id) VALUES (%s, %s)",
        (g.org_id, target_org_id)
    )
    return jsonify({"message": f"Visibility request sent to {target[0]['name']}"}), 201


@auth_bp.route("/auth/visibility/requests", methods=["GET"])
@admin_required
def pending_visibility_requests():
    """List pending visibility requests targeting MY org (admin only)."""
    rows = execute_query(
        """SELECT ovr.id, ovr.requester_org_id, ovr.status, ovr.created_at,
                  o.name AS requester_org_name, o.slug AS requester_org_slug
           FROM org_visibility_requests ovr
           JOIN organisations o ON o.id = ovr.requester_org_id
           WHERE ovr.target_org_id=%s AND ovr.status='pending'
           ORDER BY ovr.created_at DESC""",
        (g.org_id,), fetch=True
    )
    for r in rows:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
    return jsonify(rows)


@auth_bp.route("/auth/visibility/respond", methods=["POST"])
@admin_required
def respond_visibility_request():
    """
    Approve or reject a visibility request targeting my org.
    Body: { request_id, action: 'approve'|'reject' }
    """
    body = request.get_json(silent=True) or {}
    req_id = body.get("request_id")
    action = (body.get("action") or "").lower()

    if not req_id or action not in ("approve", "reject"):
        return jsonify({"error": "request_id and action ('approve'|'reject') required"}), 400

    rows = execute_query(
        "SELECT id FROM org_visibility_requests WHERE id=%s AND target_org_id=%s AND status='pending' LIMIT 1",
        (req_id, g.org_id), fetch=True
    )
    if not rows:
        return jsonify({"error": "Request not found or not pending"}), 404

    new_status = "approved" if action == "approve" else "rejected"
    execute_query(
        """UPDATE org_visibility_requests
           SET status=%s, reviewed_by=%s, reviewed_at=%s
           WHERE id=%s""",
        (new_status, g.user_id,
         datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
         req_id)
    )
    return jsonify({"message": f"Request {new_status}"})


@auth_bp.route("/auth/visibility/approved", methods=["GET"])
@login_required
def approved_orgs():
    """
    Orgs whose analyses MY org can see (approved requests sent BY my org).
    """
    rows = execute_query(
        """SELECT o.id, o.name, o.slug
           FROM org_visibility_requests ovr
           JOIN organisations o ON o.id = ovr.target_org_id
           WHERE ovr.requester_org_id=%s AND ovr.status='approved'""",
        (g.org_id,), fetch=True
    )
    return jsonify(rows)


# ══════════════════════════════════════════════════════════════
# GOOGLE OAUTH 2.0
# ══════════════════════════════════════════════════════════════

import secrets as _secrets
import urllib.parse as _urlparse
import requests as _requests
from flask import redirect, session

GOOGLE_AUTH_URL      = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL     = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_SCOPE         = "openid email profile"


@auth_bp.route("/auth/google/login")
def google_login():
    """Redirect browser → Google OAuth consent screen."""
    cfg = current_app.config
    client_id = cfg.get("GOOGLE_CLIENT_ID", "")
    if not client_id or client_id == "PASTE_YOUR_GOOGLE_CLIENT_ID_HERE":
        return jsonify({"error": "Google OAuth not configured. Add GOOGLE_CLIENT_ID to .env"}), 503

    state = _secrets.token_urlsafe(16)
    session["google_oauth_state"] = state

    base_url = cfg.get("APP_BASE_URL", "http://127.0.0.1:5000")
    redirect_uri = f"{base_url}/api/auth/google/callback"

    params = {
        "client_id":     client_id,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         GOOGLE_SCOPE,
        "state":         state,
        "access_type":   "offline",
        "prompt":        "select_account",
    }
    url = GOOGLE_AUTH_URL + "?" + _urlparse.urlencode(params)
    return redirect(url)


@auth_bp.route("/auth/google/callback")
def google_callback():
    """
    Google redirects here with ?code=...&state=...
    Exchange code for tokens, fetch user info, create/link user, issue JWT.
    """
    cfg = current_app.config
    base_url = cfg.get("APP_BASE_URL", "http://127.0.0.1:5000")

    # ── CSRF state check ──────────────────────────────────────
    returned_state = request.args.get("state", "")
    expected_state = session.pop("google_oauth_state", None)
    if not expected_state or returned_state != expected_state:
        return redirect(f"{base_url}/login?error=oauth_state_mismatch")

    code = request.args.get("code")
    if not code:
        error = request.args.get("error", "unknown")
        return redirect(f"{base_url}/login?error={error}")

    # ── Exchange code for tokens ──────────────────────────────
    redirect_uri = f"{base_url}/api/auth/google/callback"
    try:
        token_resp = _requests.post(GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     cfg.get("GOOGLE_CLIENT_ID"),
            "client_secret": cfg.get("GOOGLE_CLIENT_SECRET"),
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
        }, timeout=10)
        token_data = token_resp.json()
        if "error" in token_data:
            logger.error(f"Google token error: {token_data}")
            return redirect(f"{base_url}/login?error=google_token_failed")
        access_token_google = token_data.get("access_token")
    except Exception as e:
        logger.error(f"Google token exchange failed: {e}")
        return redirect(f"{base_url}/login?error=google_token_failed")

    # ── Fetch user info from Google ───────────────────────────
    try:
        info_resp = _requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token_google}"},
            timeout=10
        )
        guser = info_resp.json()
    except Exception as e:
        logger.error(f"Google userinfo failed: {e}")
        return redirect(f"{base_url}/login?error=google_userinfo_failed")

    google_email    = (guser.get("email") or "").strip().lower()
    google_name     = guser.get("name") or google_email.split("@")[0]
    google_verified = guser.get("email_verified", False)

    if not google_email or not google_verified:
        return redirect(f"{base_url}/login?error=google_email_unverified")

    # ── Find or create user ───────────────────────────────────
    e_hash = hash_email(google_email)
    existing = execute_query(
        """SELECT u.id, u.org_id, u.display_name, u.role, u.is_active,
                  o.name AS org_name, o.slug AS org_slug
           FROM users u JOIN organisations o ON o.id = u.org_id
           WHERE u.email_hash=%s LIMIT 1""",
        (e_hash,), fetch=True
    )

    if existing:
        # Existing user — log them in
        user = existing[0]
        if not user["is_active"]:
            return redirect(f"{base_url}/login?error=account_inactive")
    else:
        # New user — create org (named after email domain) + member account
        domain = google_email.split("@")[1]
        org_name = domain.split(".")[0].title() + " (Google)"
        slug = _slugify(org_name)

        # Handle duplicate org names
        dup = execute_query("SELECT id FROM organisations WHERE slug=%s LIMIT 1", (slug,), fetch=True)
        if dup:
            slug = slug + "-" + _secrets.token_hex(3)
            org_name = org_name + " " + _secrets.token_hex(3)

        org_id = execute_query(
            "INSERT INTO organisations (name, slug) VALUES (%s, %s)",
            (org_name, slug)
        )
        e_enc  = encrypt_email(google_email)
        # No password for Google users — store a random unusable hash
        p_hash = hash_password(_secrets.token_urlsafe(32))

        user_id = execute_query(
            """INSERT INTO users (org_id, display_name, email_enc, email_hash, password_hash, role)
               VALUES (%s, %s, %s, %s, %s, 'admin')""",
            (org_id, google_name, e_enc, e_hash, p_hash)
        )
        user = {
            "id": user_id, "org_id": org_id,
            "display_name": google_name, "role": "admin",
            "org_name": org_name, "org_slug": slug,
        }

    # ── Issue JWT tokens ──────────────────────────────────────
    at = generate_access_token(user["id"], user["org_id"], user["role"])
    raw_rt, rt_hash = generate_refresh_token()

    refresh_ttl_days = int(cfg.get("JWT_REFRESH_TTL_DAYS", 7))
    expires_at = datetime.now(timezone.utc) + timedelta(days=refresh_ttl_days)
    execute_query(
        "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
        (user["id"], rt_hash, expires_at.strftime("%Y-%m-%d %H:%M:%S"))
    )

    resp = make_response(redirect(f"{base_url}/"))
    _set_auth_cookies(resp, at, raw_rt)
    return resp
