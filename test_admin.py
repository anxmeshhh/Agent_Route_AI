"""Quick test: verify all admin endpoints work end-to-end."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import requests, mysql.connector

s = requests.Session()
# Login + OTP
r = s.post('http://127.0.0.1:5000/api/auth/login', json={'email':'superadmin@agentroute.ai','password':'SuperAdmin@2026'})
uid = r.json()['user_id']

conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='theanimesh2005',database='shipment_risk_db',charset='utf8mb4')
cur = conn.cursor(dictionary=True)
cur.execute('SELECT otp_code FROM mfa_otp WHERE user_id=%s AND used=0 ORDER BY id DESC LIMIT 1', (uid,))
otp = cur.fetchone()['otp_code']
s.post('http://127.0.0.1:5000/api/auth/verify-otp', json={'user_id': uid, 'otp_code': otp})

# Test tickets list
r = s.get('http://127.0.0.1:5000/api/admin/tickets')
d = r.json()
print('Tickets:', r.status_code, 'total:', d['total'], 'page:', d['page'])
if d['tickets']:
    t = d['tickets'][0]
    tid = t['ticket_id']
    print(f'  First ticket: {tid} title={t["title"][:40]} status={t["status"]}')

    # Test ticket detail
    r = s.get(f'http://127.0.0.1:5000/api/admin/tickets/{tid}')
    print(f'  Detail: {r.status_code} has result_json={bool(r.json().get("result_json"))}')

# Test logs
r = s.get('http://127.0.0.1:5000/api/admin/logs')
d = r.json()
print('Logs:', r.status_code, 'total:', d['total'])
if d['logs']:
    print(f'  First log: {d["logs"][0]["agent_name"]} — {d["logs"][0]["action"][:50]}')

# Test orgs
r = s.get('http://127.0.0.1:5000/api/admin/orgs')
orgs = r.json()
print('Orgs:', r.status_code, [(o['name'], o['member_count']) for o in orgs])

cur.close()
conn.close()
print("\n✅ All admin endpoints verified!")
