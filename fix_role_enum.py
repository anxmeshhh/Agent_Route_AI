import mysql.connector
conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='theanimesh2005',database='shipment_risk_db',charset='utf8mb4')
cur = conn.cursor()
cur.execute("SHOW COLUMNS FROM users LIKE 'role'")
rows = cur.fetchall()
print("Current role column:", rows)

# Fix: alter ENUM to include 'user' alongside 'member' and 'admin'
try:
    cur.execute("ALTER TABLE users MODIFY role ENUM('user','member','admin') DEFAULT 'user'")
    conn.commit()
    print("ENUM updated to include 'user'")
except Exception as e:
    print(f"Alter failed: {e}")

cur.execute("SHOW COLUMNS FROM users LIKE 'role'")
print("After:", cur.fetchall())
conn.close()
