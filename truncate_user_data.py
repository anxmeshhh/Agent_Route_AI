"""
Truncate all user/auth/shipment data tables WITHOUT dropping them.
Reference data tables (ref_*, sanctions, ports, etc.) are preserved.
"""
import mysql.connector

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root',
    password='theanimesh2005', database='shipment_risk_db', charset='utf8mb4'
)
cur = conn.cursor()

# Disable FK checks so we can truncate in any order
cur.execute("SET FOREIGN_KEY_CHECKS = 0")

TABLES_TO_CLEAR = [
    "mfa_otp",
    "refresh_tokens",
    "org_visibility_requests",
    "risk_assessments",
    "agent_logs",
    "shipments",
    "users",
    "organisations",
]

for tbl in TABLES_TO_CLEAR:
    try:
        cur.execute(f"TRUNCATE TABLE {tbl}")
        print(f"  TRUNCATED: {tbl}")
    except Exception as e:
        print(f"  SKIP {tbl}: {e}")

# Re-enable FK checks
cur.execute("SET FOREIGN_KEY_CHECKS = 1")

# Re-insert the default organisation (required by shipments FK)
cur.execute(
    "INSERT IGNORE INTO organisations (id, name, slug) VALUES (1, 'Default Organisation', 'default')"
)
conn.commit()
print("\nDefault organisation restored.")

cur.close()
conn.close()
print("\nDone — all user/auth/shipment data cleared. Reference data intact.")
