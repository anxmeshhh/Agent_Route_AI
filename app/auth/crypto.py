"""
app/auth/crypto.py — Cryptographic helpers

Provides:
  - Fernet symmetric encryption for PII (email) stored in DB
  - bcrypt for password hashing
  - SHA-256 for deterministic email lookup (without exposing plaintext)
  - JWT access token + refresh token generation & verification

Green mandatory: PII not in frontend calls, PII encrypted in DB.
Yellow advantage: JWT access + refresh token pair in HttpOnly cookies.
"""
import os
import hashlib
import secrets
import logging
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from flask import current_app

logger = logging.getLogger(__name__)


# ── Fernet (PII Encryption) ───────────────────────────────────

def _get_fernet():
    """Return a Fernet cipher instance using config key."""
    from cryptography.fernet import Fernet, InvalidToken  # lazy import
    key = current_app.config.get("FERNET_KEY", "")
    if not key:
        # Generate an ephemeral key in dev mode — warn loudly
        logger.warning(
            "⚠️  FERNET_KEY not set — generating ephemeral key. "
            "Encrypted emails CANNOT be decrypted after restart!"
        )
        key = Fernet.generate_key().decode()
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_email(email: str) -> bytes:
    """Encrypt a plaintext email → VARBINARY for DB storage."""
    f = _get_fernet()
    return f.encrypt(email.lower().strip().encode())


def decrypt_email(email_enc: bytes) -> str:
    """Decrypt email_enc → plaintext email."""
    try:
        f = _get_fernet()
        return f.decrypt(email_enc).decode()
    except Exception:
        return "<encrypted>"


def hash_email(email: str) -> str:
    """SHA-256 of normalised email — used for DB lookup without exposing PII."""
    normalised = email.lower().strip()
    return hashlib.sha256(normalised.encode()).hexdigest()


# ── bcrypt (Password) ─────────────────────────────────────────

def hash_password(plaintext: str) -> str:
    """Hash a plaintext password with bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plaintext.encode(), salt).decode()


def verify_password(plaintext: str, hashed: str) -> bool:
    """Return True if plaintext matches the bcrypt hash."""
    try:
        return bcrypt.checkpw(plaintext.encode(), hashed.encode())
    except Exception:
        return False


# ── JWT (Access + Refresh Tokens) ────────────────────────────

def _jwt_secret() -> str:
    return current_app.config.get("JWT_SECRET", "dev-secret")


def generate_access_token(user_id: int, org_id: int, role: str) -> str:
    """Issue a short-lived JWT access token (15 min default)."""
    ttl = current_app.config.get("JWT_ACCESS_TTL_MINUTES", 15)
    payload = {
        "sub": str(user_id),   # JWT spec requires sub to be a string
        "org": org_id,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ttl),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def generate_refresh_token() -> tuple[str, str]:
    """
    Generate a cryptographically secure refresh token.
    Returns (raw_token, sha256_hash_for_db).
    Only the hash is stored in DB — raw is sent in HttpOnly cookie.
    """
    raw = secrets.token_urlsafe(48)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def verify_access_token(token: str) -> dict | None:
    """
    Verify and decode a JWT access token.
    Returns payload dict or None on failure.
    """
    try:
        # Disable strict subject validation to accept both int and string sub
        payload = jwt.decode(
            token, _jwt_secret(), algorithms=["HS256"],
            options={"verify_sub": False}
        )
        if payload.get("type") != "access":
            return None
        # Ensure sub is always an int for downstream use
        try:
            payload["sub"] = int(payload["sub"])
        except (ValueError, TypeError):
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Access token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"Invalid access token: {e}")
        return None

