import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.intake_agent import IntakeAgent

agent = IntakeAgent()

queries = [
    "Pharmaceutical shipment from Delhi to Thiruvananthapuram Kerala in 3 days urgent",
    "Electronics cargo from Mumbai to Bangalore by road in 2 days",
    "General cargo from Delhi to Kolkata by road NH19 in 48 hours",
    "Electronics from Shanghai to Rotterdam via Suez Canal 28 days transit",
    "Automotive parts from Hamburg to Mumbai in 14 days maritime",
]

print("=" * 70)
print("INTAKE AGENT DIRECTION-AWARE TEST")
print("=" * 70)

all_pass = True
for q in queries:
    r = agent.run(q, "test-session")
    origin = r["origin_port"] or "MISSING"
    dest   = r["port"] or "MISSING"
    eta    = r["eta_days"]
    cargo  = r["cargo_type"]
    
    collision = origin == dest
    missing   = "MISSING" in [origin, dest]
    status    = "FAIL" if (collision or missing) else "OK"
    if status == "FAIL":
        all_pass = False
    
    print(f"[{status}] {q[:58]}...")
    print(f"      origin={origin}  dest={dest}  eta={eta}d  cargo={cargo}")
    if collision:
        print("      *** COLLISION: origin == dest! ***")
    if missing:
        print("      *** MISSING: origin or dest is None! ***")
    print()

print("=" * 70)
print("RESULT:", "ALL PASS" if all_pass else "FAILURES DETECTED")
print("=" * 70)
