import httpx, sys

BASE = "http://127.0.0.1:8520"

# Login
login_payload = {"identifier": "trace_user", "password": "password123"}
print('LOGIN ->', login_payload)
try:
    r = httpx.post(f"{BASE}/auth/login", json=login_payload, timeout=10.0)
except Exception as e:
    print('LOGIN ERR', e)
    sys.exit(2)
print('LOGIN', r.status_code, r.text)
if r.status_code != 200:
    sys.exit(1)

tokens = r.json()

# Refresh
try:
    rr = httpx.post(f"{BASE}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}, timeout=10.0)
except Exception as e:
    print('REFRESH ERR', e)
    sys.exit(2)
print('REFRESH', rr.status_code, rr.text)

# Logout
try:
    lo = httpx.post(f"{BASE}/auth/logout", json={"refresh_token": tokens["refresh_token"]}, timeout=10.0)
except Exception as e:
    print('LOGOUT ERR', e)
    sys.exit(2)
print('LOGOUT', lo.status_code, lo.text)
