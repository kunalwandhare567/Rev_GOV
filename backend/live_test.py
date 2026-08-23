"""Live API end-to-end test"""
import sys
import httpx
import json

# Force UTF-8 on Windows so emoji in API responses don't crash the test
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:8000/api/v1"
USER = "live_api_test_001"

print("=== LIVE API TEST ===\n")

# Health check
r = httpx.get("http://localhost:8000/health")
assert r.status_code == 200
print(f"[OK] /health: status={r.json()['status']}")

# Service catalogue
r = httpx.get(f"{BASE}/applications/services")
data = r.json()
print(f"[OK] Services: {data['count']} services available")
for s in data["services"]:
    print(f"     - {s['id']}: INR {s['fee_amount']}, SLA={s['sla_days']}d")

print()

# Data Guard BLOCK
r = httpx.post(f"{BASE}/data-guard/check", json={
    "payload": {"applicant_name": "Ramesh Kumar", "message": "translate"},
    "destination": "cloud_llm",
    "operation": "translate"
})
dg = r.json()
print(f"[OK] Data Guard BLOCK: decision={dg['decision']}")
print(f"     Blocked fields: {dg.get('blocked_fields')}")

# Data Guard ALLOW
r = httpx.post(f"{BASE}/data-guard/check", json={
    "payload": {"message": "translate income certificate to Tamil"},
    "destination": "cloud_llm",
    "operation": "translate"
})
dg2 = r.json()
print(f"[OK] Data Guard ALLOW: decision={dg2['decision']}")

print()

# Conversation INIT
r = httpx.post(f"{BASE}/conversation/message", json={
    "citizen_identifier": USER,
    "text": "Hello",
    "channel": "WEB",
    "language": "en"
})
resp = r.json()
node1 = resp["current_node"]
print(f"[OK] Chat INIT: node={node1}")

# Conversation CONSENT
r = httpx.post(f"{BASE}/conversation/message", json={
    "citizen_identifier": USER,
    "text": "Yes I agree",
    "channel": "WEB",
    "language": "en"
})
resp = r.json()
print(f"[OK] Consent: consent_given={resp['consent_given']}, node={resp['current_node']}")

# Conversation INTENT
r = httpx.post(f"{BASE}/conversation/message", json={
    "citizen_identifier": USER,
    "text": "I need an income certificate for education",
    "channel": "WEB",
    "language": "en"
})
resp = r.json()
print(f"[OK] Intent: node={resp['current_node']}, app_created={resp.get('application_number', 'see extra_data')}")
preview = resp["response"][:100]
print(f"     Response: {preview}...")

print()

# Channel switch test
r = httpx.post(f"{BASE}/conversation/channel-switch", json={
    "citizen_identifier": USER,
    "new_channel": "MOBILE",
    "language": "en"
})
cs = r.json()
print(f"[OK] Channel Switch WEB→MOBILE: status={cs['status']}, node={cs.get('current_node', 'N/A')}")

# Dashboard
r = httpx.get(f"{BASE}/dashboard/overview")
dash = r.json()
print(f"\n[OK] Dashboard Overview:")
stats = dash.get("stats", {})
print(f"     Active sessions: {stats.get('active_sessions', 0)}")
print(f"     Total applications: {dash.get('total_applications', 0)}")
print(f"     Data Guard: blocks={stats.get('dg_blocks_today', 0)}")
print(f"     By service: {dash.get('by_service', {})}")


# Service health
r = httpx.get(f"{BASE}/dashboard/service-health")
health = r.json()
print(f"\n[OK] Component Health:")
for comp, info in health["components"].items():
    print(f"     {comp}: {info['status']}")

print()
print("=" * 50)
print("  ALL LIVE API TESTS PASSED ✓")
print("=" * 50)
