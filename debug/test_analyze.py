"""Test analyze as org_id=2 user"""
import sys, io, requests, mysql.connector
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

s = requests.Session()

# Login as Animesh
r = s.post('http://127.0.0.1:5000/api/auth/login', json={'email':'theanimeshgupta@gmail.com','password':'test'})
data = r.json()
print('Login:', r.status_code, data)

if data.get('otp_required'):
    uid = data['user_id']
    conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='theanimesh2005',database='shipment_risk_db',charset='utf8mb4')
    cur = conn.cursor(dictionary=True)
    cur.execute('SELECT otp_code FROM mfa_otp WHERE user_id=%s AND used=0 ORDER BY id DESC LIMIT 1', (uid,))
    otp_row = cur.fetchone()
    if otp_row:
        r2 = s.post('http://127.0.0.1:5000/api/auth/verify-otp', json={'user_id':uid, 'otp_code':otp_row['otp_code']})
        print('OTP verify:', r2.status_code, r2.json())
    cur.close(); conn.close()

# Test GET /api/auth/me
r = s.get('http://127.0.0.1:5000/api/auth/me')
print('Me:', r.status_code, r.json() if r.ok else r.text[:100])

# Test analyze TKT-00019
print('\nAnalyzing TKT-00019...')
r = s.post('http://127.0.0.1:5000/api/tickets/TKT-00019/analyze')
print('Status:', r.status_code)
ct = r.headers.get('content-type','?')
print('Content-Type:', ct)
if 'json' in ct:
    print('Body:', r.json())
else:
    print('Body (HTML):', r.text[:300])
