import httpx
payload = {
    "username": "trace_user",
    "email": "trace_user@example.com",
    "password": "password123",
    "phone": "+260971000002",
    "role": "msme"
}
resp = httpx.post('http://127.0.0.1:8500/auth/register', json=payload, timeout=10.0)
print('STATUS', resp.status_code)
print(resp.text)
