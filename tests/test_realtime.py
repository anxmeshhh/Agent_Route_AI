import requests, json, time

# 1. Start analysis with named vessel
print("=== POSTING ANALYSIS ===")
r = requests.post(
    "http://127.0.0.1:5000/api/analyze",
    json={"query": "Ship electronics from Shanghai to Rotterdam via MV Atlas Star, ETA 28 days"},
    timeout=15
)
print("Status:", r.status_code)
d = r.json()
sid = d.get("session_id")
print("Session:", sid)

# 2. Wait for pipeline
print("\n=== WAITING 40s FOR 7-AGENT PIPELINE ===")
time.sleep(40)

# 3. Get result
r2 = requests.get(f"http://127.0.0.1:5000/api/result/{sid}", timeout=15)
res = r2.json()
print("Risk Level :", res.get("risk_level"), "/", res.get("risk_score"), "/100")
print("LLM Model  :", res.get("llm_model"))
print("LLM Tokens :", res.get("llm_tokens_used"))
print("Factors    :", len(res.get("factors", [])))

# 4. Test departure window with real OWM
print("\n=== REAL OWM 5-DAY DEPARTURE FORECAST ===")
r3 = requests.get(
    "http://127.0.0.1:5000/api/route-analysis",
    params={
        "origin": "Shanghai", "dest": "Rotterdam", "port_city": "Rotterdam",
        "risk_score": 65, "cargo_type": "electronics", "eta_days": 28
    },
    timeout=20
)
dep = r3.json().get("departure_window", {})
print("Data source :", dep.get("data_source"))
print("Recommendation:", dep.get("recommendation"))
fc = dep.get("5_day_forecast", [])
for i, day in enumerate(fc[:3]):
    print(f"  Day {i+1}: {day.get('day_label')} | risk={day.get('risk_index')} | {day.get('condition','N/A')} | wind={day.get('wind_ms','N/A')}m/s")
print("Total forecast days:", len(fc))
