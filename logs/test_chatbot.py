"""Quick test: reproduce the chatbot timeout issue."""
import httpx
import time

BASE = "http://localhost:3000"

# Step 1: Login first
print("=== Step 1: Login ===")
r = httpx.post(f"{BASE}/rest/user/login", json={"email": "admin@juice-sh.op", "password": "admin123"}, timeout=10)
print(f"Login: {r.status_code}")
token = r.json().get("authentication", {}).get("token", "")
auth = {"Authorization": f"Bearer {token}"}
print(f"Token: {token[:30]}...")

# Step 2: Check chatbot status
print("\n=== Step 2: GET /rest/chatbot/status ===")
r = httpx.get(f"{BASE}/rest/chatbot/status", headers=auth, timeout=10)
print(f"Status: {r.status_code} -> {r.text}")

# Step 3: Try POST /rest/chatbot/respond with JSON body
print("\n=== Step 3: POST /rest/chatbot/respond (JSON body) ===")
t0 = time.time()
try:
    r = httpx.post(f"{BASE}/rest/chatbot/respond", json={"body": "test"}, headers=auth, timeout=10)
    print(f"Respond (json): {r.status_code} -> {r.text[:300]} ({time.time()-t0:.1f}s)")
except Exception as e:
    print(f"Respond (json) FAILED: {e} ({time.time()-t0:.1f}s)")

# Step 4: Try with query param instead
print("\n=== Step 4: POST /rest/chatbot/respond (query param) ===")
t0 = time.time()
try:
    r = httpx.post(f"{BASE}/rest/chatbot/respond", params={"body": "test"}, headers=auth, timeout=10)
    print(f"Respond (query): {r.status_code} -> {r.text[:300]} ({time.time()-t0:.1f}s)")
except Exception as e:
    print(f"Respond (query) FAILED: {e} ({time.time()-t0:.1f}s)")

# Step 5: Try with form data
print("\n=== Step 5: POST /rest/chatbot/respond (form data) ===")
t0 = time.time()
try:
    r = httpx.post(f"{BASE}/rest/chatbot/respond", data={"body": "test"}, headers=auth, timeout=10)
    print(f"Respond (form): {r.status_code} -> {r.text[:300]} ({time.time()-t0:.1f}s)")
except Exception as e:
    print(f"Respond (form) FAILED: {e} ({time.time()-t0:.1f}s)")

# Step 6: Try with different content-type
print("\n=== Step 6: POST /rest/chatbot/respond (explicit content-type) ===")
t0 = time.time()
try:
    r = httpx.post(f"{BASE}/rest/chatbot/respond", 
                   json={"action": "namequery", "body": "admin"},
                   headers={**auth, "Content-Type": "application/json"},
                   timeout=10)
    print(f"Respond (explicit CT): {r.status_code} -> {r.text[:300]} ({time.time()-t0:.1f}s)")
except Exception as e:
    print(f"Respond (explicit CT) FAILED: {e} ({time.time()-t0:.1f}s)")
