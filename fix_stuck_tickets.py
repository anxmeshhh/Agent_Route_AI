"""Reset all stuck in_progress tickets to open."""
import mysql.connector

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root',
    password='theanimesh2005', database='shipment_risk_db', charset='utf8mb4'
)
cur = conn.cursor()
cur.execute("UPDATE shipment_tickets SET status='open' WHERE status='in_progress'")
conn.commit()
print(f"Reset {cur.rowcount} stuck ticket(s)")
cur.close()
conn.close()
