"""
migrate_superadmin.py — Add superadmin role + seed first superadmin user.
Run once:  python migrate_superadmin.py
Idempotent — safe to run multiple times.
"""
import os, sys, logging
import mysql.connector
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

def run():
    try:
        conn = mysql.connector.connect(**DB)
        cur = conn.cursor()
        log.info(f"Connected to {DB['database']}")
    except mysql.connector.Error as e:
        log.error(f"DB connect failed: {e}")
        sys.exit(1)

    # 1. Extend role ENUM to include 'superadmin'
    try:
        cur.execute("""
            ALTER TABLE users
            MODIFY COLUMN role ENUM('user','member','admin','superadmin') DEFAULT 'user'
        """)
        conn.commit()
        log.info("✓ users.role ENUM extended → includes 'superadmin'")
    except mysql.connector.Error as e:
        if "Duplicate" in str(e) or e.errno in (1060,):
            log.info("  role ENUM already includes superadmin — skipping")
        else:
            log.warning(f"  role ALTER: {e}")

    # 2. Add system_logs table for application-level logging
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                level       VARCHAR(16) NOT NULL DEFAULT 'INFO',
                module      VARCHAR(64),
                message     TEXT NOT NULL,
                details     JSON,
                created_at  DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
                INDEX idx_level     (level),
                INDEX idx_module    (module),
                INDEX idx_created   (created_at)
            ) ENGINE=InnoDB
        """)
        conn.commit()
        log.info("✓ system_logs table ready")
    except mysql.connector.Error as e:
        if e.errno == 1050:
            log.info("  system_logs already exists")
        else:
            log.warning(f"  system_logs: {e}")

    # 3. Seed superadmin user (if not exists)
    try:
        # Check if superadmin already exists
        cur.execute("SELECT id FROM users WHERE role='superadmin' LIMIT 1")
        existing = cur.fetchone()
        if existing:
            log.info(f"  Superadmin already exists (user_id={existing[0]}) — skipping seed")
        else:
            # We need crypto functions to hash the password and encrypt email
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from app.auth.crypto import hash_password, hash_email, encrypt_email

                email = "superadmin@agentroute.ai"
                password = "SuperAdmin@2026"
                display_name = "System Admin"

                e_hash = hash_email(email)
                e_enc = encrypt_email(email)
                p_hash = hash_password(password)

                # Ensure default org exists
                cur.execute("SELECT id FROM organisations WHERE id=1")
                if not cur.fetchone():
                    cur.execute("INSERT INTO organisations (id, name, slug) VALUES (1, 'Default Organisation', 'default')")

                cur.execute("""
                    INSERT INTO users (org_id, display_name, email_enc, email_hash, password_hash, role, is_active)
                    VALUES (1, %s, %s, %s, %s, 'superadmin', 1)
                """, (display_name, e_enc, e_hash, p_hash))
                conn.commit()
                log.info(f"✓ Superadmin seeded: {email} / {password}")
                log.info("  ⚠ CHANGE THIS PASSWORD after first login!")
            except Exception as e:
                log.warning(f"  Superadmin seed failed (manual creation needed): {e}")
                conn.rollback()
    except mysql.connector.Error as e:
        log.warning(f"  Superadmin check: {e}")

    cur.close()
    conn.close()
    log.info("\n✅ Superadmin migration complete!")


if __name__ == "__main__":
    run()
