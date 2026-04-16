"""
seed_superadmin.py — Create a superadmin user directly in the database.
Standalone script (does NOT require Flask app context).
Run:  python seed_superadmin.py
"""
import os, sys, hashlib, logging
import mysql.connector
import bcrypt
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DB = {
    "host":     os.getenv("MYSQL_HOST", "localhost"),
    "port":     int(os.getenv("MYSQL_PORT", "3306")),
    "user":     os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "shipment_risk_db"),
    "charset":  "utf8mb4",
}

# ── The superadmin credentials ──
SA_EMAIL    = "superadmin@agentroute.ai"
SA_PASSWORD = "SuperAdmin@2026"
SA_NAME     = "System Admin"

def main():
    conn = mysql.connector.connect(**DB)
    cur = conn.cursor(dictionary=True)

    # Email hash (SHA-256 — same as crypto.py hash_email)
    e_hash = hashlib.sha256(SA_EMAIL.lower().strip().encode()).hexdigest()

    # Check if superadmin already exists
    cur.execute("SELECT id, role FROM users WHERE email_hash=%s LIMIT 1", (e_hash,))
    row = cur.fetchone()
    if row:
        if row["role"] == "superadmin":
            log.info(f"Superadmin already exists (id={row['id']}) — nothing to do.")
        else:
            cur.execute("UPDATE users SET role='superadmin' WHERE id=%s", (row["id"],))
            conn.commit()
            log.info(f"Promoted user #{row['id']} to superadmin.")
        cur.close(); conn.close()
        return

    # Encrypt email with Fernet (needs key from .env)
    fernet_key = os.getenv("FERNET_KEY", "")
    if fernet_key:
        from cryptography.fernet import Fernet
        if isinstance(fernet_key, str):
            fernet_key = fernet_key.encode()
        f = Fernet(fernet_key)
        e_enc = f.encrypt(SA_EMAIL.lower().strip().encode())
    else:
        # If no Fernet key, store a placeholder (login will still work via email_hash)
        log.warning("⚠ FERNET_KEY not set — storing placeholder for email_enc")
        e_enc = b"<no-fernet-key>"

    # Password hash (bcrypt — same as crypto.py hash_password)
    p_hash = bcrypt.hashpw(SA_PASSWORD.encode(), bcrypt.gensalt(rounds=12)).decode()

    # Ensure default org exists
    cur.execute("SELECT id FROM organisations WHERE id=1")
    if not cur.fetchone():
        cur.execute("INSERT INTO organisations (id, name, slug) VALUES (1, 'Default Organisation', 'default')")

    cur.execute("""
        INSERT INTO users (org_id, display_name, email_enc, email_hash, password_hash, role, is_active)
        VALUES (1, %s, %s, %s, %s, 'superadmin', 1)
    """, (SA_NAME, e_enc, e_hash, p_hash))
    conn.commit()
    log.info(f"✅ Superadmin created: {SA_EMAIL} / {SA_PASSWORD}")
    log.info("   ⚠ Change this password after first login!")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
