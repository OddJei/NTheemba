import httpx
import uuid
import datetime

payload = {
    "event_id": str(uuid.uuid4()),
    "business_id": "b1b3ef04-5261-430c-8ca0-d972a4dd0f45",
    "plan": "paid",
    "paid_until": (datetime.datetime.utcnow() + datetime.timedelta(days=30)).isoformat() + "Z",
    "amount": 200.0,
    "currency": "ZMW",
    "reference_id": "test-deposit-1",
    # Include depositId (camelCase) so the deposit callback can correlate
    # with persisted PaymentInitiation.deposit_id
    "depositId": "test-deposit-1",
}
print("Posting payment callback (hyphenated endpoint):", payload)
try:
    # Use the deposit callback endpoint (preferred callback path)
    r = httpx.post("http://127.0.0.1:8500/callbacks/payments/deposits", json=payload, timeout=10.0)
    print(r.status_code)
    print(r.text)
except Exception as e:
    print("Request failed:", e)
