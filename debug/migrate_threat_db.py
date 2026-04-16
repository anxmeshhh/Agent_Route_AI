"""
Complete migration: 
1. Add ticket tables to schema if not exists
2. ALTER result_json column to JSON type (from MEDIUMTEXT)
3. Add threat_json + reroute_json columns
"""
import mysql.connector

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root',
    password='theanimesh2005', database='shipment_risk_db', charset='utf8mb4'
)
cur = conn.cursor()

# 1. Ensure ticket tables exist
cur.execute("""
CREATE TABLE IF NOT EXISTS shipment_tickets (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ticket_id      VARCHAR(20)  NOT NULL UNIQUE,
    shipment_uuid  VARCHAR(36)  NOT NULL,
    org_id         INT UNSIGNED DEFAULT 1,
    user_id        INT UNSIGNED,
    title          VARCHAR(256) NOT NULL,
    transport_mode ENUM('road','sea','air') DEFAULT 'road',
    cargo_type     VARCHAR(128) DEFAULT 'general',
    weight_kg      DECIMAL(10,2),
    budget_usd     DECIMAL(12,2),
    eta_days       TINYINT UNSIGNED,
    origin         VARCHAR(128),
    destination    VARCHAR(128),
    priority       ENUM('low','medium','high','critical') DEFAULT 'medium',
    status         ENUM('open','in_progress','completed','failed','closed') DEFAULT 'open',
    session_id     VARCHAR(36),
    result_json    JSON,
    threat_json    JSON,
    reroute_json   JSON,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (org_id) REFERENCES organisations(id),
    INDEX idx_shipment (shipment_uuid),
    INDEX idx_status   (status),
    INDEX idx_org      (org_id)
) ENGINE=InnoDB
""")
print("shipment_tickets: OK")

cur.execute("""
CREATE TABLE IF NOT EXISTS ticket_sequence (
    next_val INT UNSIGNED NOT NULL DEFAULT 1
) ENGINE=InnoDB
""")
cur.execute("SELECT COUNT(*) FROM ticket_sequence")
if cur.fetchone()[0] == 0:
    cur.execute("INSERT INTO ticket_sequence VALUES (1)")
print("ticket_sequence: OK")

# 2. Try to alter result_json to JSON (idempotent)
try:
    cur.execute("ALTER TABLE shipment_tickets MODIFY COLUMN result_json JSON")
    print("result_json -> JSON: OK")
except mysql.connector.Error as e:
    print(f"result_json alter: {e} (may already be JSON)")

# 3. Add threat_json and reroute_json columns if not exist
for col in ['threat_json', 'reroute_json']:
    try:
        cur.execute(f"ALTER TABLE shipment_tickets ADD COLUMN {col} JSON")
        print(f"{col}: ADDED")
    except mysql.connector.Error as e:
        if e.errno == 1060:  # duplicate column
            print(f"{col}: already exists")
        else:
            print(f"{col}: {e}")

conn.commit()
cur.close()
conn.close()
print("\nMigration complete.")
