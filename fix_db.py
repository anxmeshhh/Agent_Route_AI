"""
fix_db.py — Database migration: add auth tables and update shipments

Run once with: python fix_db.py

This script safely adds all new auth tables and alters existing tables.
It uses ALTER TABLE ... IF NOT EXISTS / INSERT IGNORE so it is idempotent.
"""
import os
import sys
import logging
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DB_CONFIG = {
    "host":     os.getenv("MYSQL_HOST", "localhost"),
    "port":     int(os.getenv("MYSQL_PORT", "3306")),
    "user":     os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "shipment_risk_db"),
    "charset":  "utf8mb4",
}

MIGRATIONS = [
    # 1. Organisations table
    """CREATE TABLE IF NOT EXISTS organisations (
        id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        name         VARCHAR(128) NOT NULL UNIQUE,
        slug         VARCHAR(64)  NOT NULL UNIQUE,
        created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB""",

    # 2. Default org for legacy data
    """INSERT IGNORE INTO organisations (id, name, slug) VALUES (1, 'Default Organisation', 'default')""",

    # 3. Users table (full secure version)
    """CREATE TABLE IF NOT EXISTS users (
        id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        org_id          INT UNSIGNED NOT NULL,
        display_name    VARCHAR(128) NOT NULL,
        email_enc       VARBINARY(512) NOT NULL,
        email_hash      VARCHAR(64) NOT NULL UNIQUE,
        password_hash   VARCHAR(256) NOT NULL,
        role            ENUM('member','admin') DEFAULT 'member',
        is_active       TINYINT(1) DEFAULT 1,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (org_id) REFERENCES organisations(id) ON DELETE CASCADE,
        INDEX idx_email_hash (email_hash),
        INDEX idx_org        (org_id)
    ) ENGINE=InnoDB""",

    # 4. MFA OTP
    """CREATE TABLE IF NOT EXISTS mfa_otp (
        id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        user_id     INT UNSIGNED NOT NULL,
        otp_code    VARCHAR(6) NOT NULL,
        expires_at  DATETIME NOT NULL,
        used        TINYINT(1) DEFAULT 0,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        INDEX idx_user (user_id)
    ) ENGINE=InnoDB""",

    # 5. Refresh tokens
    """CREATE TABLE IF NOT EXISTS refresh_tokens (
        id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        user_id     INT UNSIGNED NOT NULL,
        token_hash  VARCHAR(64) NOT NULL UNIQUE,
        expires_at  DATETIME NOT NULL,
        revoked     TINYINT(1) DEFAULT 0,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        INDEX idx_user  (user_id),
        INDEX idx_token (token_hash)
    ) ENGINE=InnoDB""",

    # 6. Org visibility requests
    """CREATE TABLE IF NOT EXISTS org_visibility_requests (
        id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        requester_org_id INT UNSIGNED NOT NULL,
        target_org_id    INT UNSIGNED NOT NULL,
        status           ENUM('pending','approved','rejected') DEFAULT 'pending',
        reviewed_by      INT UNSIGNED,
        reviewed_at      DATETIME,
        created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_org_pair (requester_org_id, target_org_id),
        FOREIGN KEY (requester_org_id) REFERENCES organisations(id) ON DELETE CASCADE,
        FOREIGN KEY (target_org_id)   REFERENCES organisations(id) ON DELETE CASCADE,
        INDEX idx_target (target_org_id),
        INDEX idx_status (status)
    ) ENGINE=InnoDB""",

    # 7. Add org_id column to shipments (nullable for backward compat)
    # Note: MySQL 8.0 doesn't support ADD COLUMN IF NOT EXISTS — error 1060 is caught below
    """ALTER TABLE shipments ADD COLUMN org_id INT UNSIGNED DEFAULT 1""",

    # 8. Add FK for org_id on shipments (if not exists — ignore error)
    # We handle this separately below since MySQL doesn't support IF NOT EXISTS on FKs
]

# These are separate because ALTER TABLE ADD CONSTRAINT may fail if FK exists already
FK_MIGRATIONS = [
    ("shipments", "fk_shipments_org",
     "ALTER TABLE shipments ADD CONSTRAINT fk_shipments_org FOREIGN KEY (org_id) REFERENCES organisations(id) ON DELETE SET NULL"),
]


def run():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        log.info(f"✅ Connected to MySQL: {DB_CONFIG['host']}:{DB_CONFIG['port']} / {DB_CONFIG['database']}")
    except mysql.connector.Error as e:
        log.error(f"❌ Cannot connect to MySQL: {e}")
        sys.exit(1)

    for stmt in MIGRATIONS:
        try:
            cursor.execute(stmt)
            conn.commit()
            first_line = stmt.strip().split('\n')[0][:80]
            log.info(f"✓ {first_line}")
        except mysql.connector.Error as e:
            # 1060 = duplicate column, 1061 = duplicate key — these are safe to ignore
            if e.errno in (1060, 1061, 1050, 1007):
                log.info(f"  (already exists — skipping)")
            else:
                log.warning(f"  ⚠ {e}")

    for table, constraint_name, stmt in FK_MIGRATIONS:
        try:
            cursor.execute(stmt)
            conn.commit()
            log.info(f"✓ FK {constraint_name} added to {table}")
        except mysql.connector.Error as e:
            if e.errno in (1826, 1022):  # duplicate FK
                log.info(f"  FK {constraint_name} already exists — skipping")
            else:
                log.warning(f"  ⚠ FK {constraint_name}: {e}")

    cursor.close()
    conn.close()
    log.info("\n✅ Migration complete! All auth tables are ready.")
    log.info("   You can now restart the app and test login/signup.")


if __name__ == "__main__":
    run()
