"""Probe Juice Shop for the correct reset endpoint."""
import httpx

BASE = "http://localhost:3000"

# Check current status
r = httpx.get(f"{BASE}/api/Challenges/", timeout=10)
challenges = r.json().get("data", [])
solved = [c for c in challenges if c.get("solved")]
print(f"Currently solved: {len(solved)}/{len(challenges)}")

# Try various known reset endpoints
endpoints = [
    ("POST", "/rest/admin/application-configuration", None),
    ("POST", "/api/Challenges/continueCode/apply/undefined", None),
    ("PUT",  "/rest/continue-code/apply/bnVsbA==", None),
    ("GET",  "/rest/admin/application-configuration", None),
    ("POST", "/rest/user/data-export", {"format": "1"}),
    ("GET",  "/api/Quantitys/", None),  # just probing
    ("POST", "/api/Challenges/repeatNotification", None),
    # The real one: Juice Shop uses a dataerasure endpoint or DB wipe
    ("POST", "/rest/user/erasure", None),
    ("DELETE", "/api/Challenges/", None),
]

print("\n--- Probing endpoints ---")
for method, path, body in endpoints:
    try:
        if method == "GET":
            r = httpx.get(f"{BASE}{path}", timeout=5)
        elif method == "POST":
            r = httpx.post(f"{BASE}{path}", json=body, timeout=5)
        elif method == "PUT":
            r = httpx.put(f"{BASE}{path}", json=body, timeout=5)
        elif method == "DELETE":
            r = httpx.delete(f"{BASE}{path}", timeout=5)
        print(f"  {method:6s} {path:50s} -> {r.status_code} {r.text[:100]}")
    except Exception as e:
        print(f"  {method:6s} {path:50s} -> ERROR: {e}")

# Try the hacky approach: get a "clean" continueCode and apply it
# Actually, the right approach is to use Juice Shop's /rest/continue-code API
print("\n--- Continue code approach ---")
try:
    # Get current continue code (to understand format)
    r = httpx.get(f"{BASE}/rest/continue-code", timeout=5)
    print(f"  GET /rest/continue-code -> {r.status_code} {r.text[:200]}")
except Exception as e:
    print(f"  GET /rest/continue-code -> ERROR: {e}")

# A continue code that represents 0 solved challenges would reset everything
# Let's try applying an empty/minimal continue code
import base64, zlib
try:
    # Try various "empty" codes
    for code_label, code in [
        ("empty base64", base64.b64encode(b"{}").decode()),
        ("literal 'reset'", "reset"),
    ]:
        r = httpx.put(f"{BASE}/rest/continue-code/apply/{code}", timeout=5)
        print(f"  PUT /rest/continue-code/apply/{code_label} -> {r.status_code} {r.text[:100]}")
except Exception as e:
    print(f"  Continue code apply error: {e}")
