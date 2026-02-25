import requests

r = requests.post(
    "http://127.0.0.1:8570/internal/debug/emit_notification",
    headers={"X-Internal-Secret": "test-internal-secret"},
    json={"channel": "in_app", "business_id": "debug-business", "payload": {"test": "hello"}},
)
print(r.status_code)
print(r.text)
