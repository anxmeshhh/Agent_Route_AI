"""
app/auth/decorators.py — Auth decorators

@login_required  — Validates JWT access token from HttpOnly cookie.
                   Injects g.user_id, g.org_id, g.role into request context.
@admin_required  — Same as login_required, but also checks role == 'admin'.
"""
import logging
from functools import wraps

from flask import request, jsonify, g

from .crypto import verify_access_token

logger = logging.getLogger(__name__)


def _extract_token() -> str | None:
    """Try cookie first, then Authorization: Bearer header (for testing)."""
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    return token or None


def login_required(f):
    """
    Decorator: requires a valid JWT access token.
    Sets g.user_id, g.org_id, g.role on success.
    Returns 401 JSON on failure.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Authentication required", "code": "NO_TOKEN"}), 401

        payload = verify_access_token(token)
        if not payload:
            return jsonify({"error": "Token expired or invalid", "code": "INVALID_TOKEN"}), 401

        g.user_id = payload["sub"]
        g.org_id  = payload["org"]
        g.role    = payload.get("role", "user")  # 'user' | 'admin'
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    """
    Decorator: requires valid JWT + role == 'admin'.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Authentication required", "code": "NO_TOKEN"}), 401

        payload = verify_access_token(token)
        if not payload:
            return jsonify({"error": "Token expired or invalid", "code": "INVALID_TOKEN"}), 401

        if payload.get("role") not in ("admin", "superadmin"):
            return jsonify({"error": "Admin access required", "code": "FORBIDDEN"}), 403

        g.user_id = payload["sub"]
        g.org_id  = payload["org"]
        g.role    = payload.get("role", "user")
        return f(*args, **kwargs)

    return decorated


def superadmin_required(f):
    """
    Decorator: requires valid JWT + role == 'superadmin'.
    Only system-wide administrators can access these endpoints.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Authentication required", "code": "NO_TOKEN"}), 401

        payload = verify_access_token(token)
        if not payload:
            return jsonify({"error": "Token expired or invalid", "code": "INVALID_TOKEN"}), 401

        if payload.get("role") != "superadmin":
            return jsonify({"error": "Super Admin access required", "code": "FORBIDDEN"}), 403

        g.user_id = payload["sub"]
        g.org_id  = payload["org"]
        g.role    = payload.get("role", "user")
        return f(*args, **kwargs)

    return decorated

