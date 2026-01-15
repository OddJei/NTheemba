from datetime import datetime, timedelta, timezone


def test_business_register_lookup_and_payment_success(client):
    payload = {
        "owner": {
            "username": "owner1",
            "email": "owner1@example.com",
            "phone": "+260700000010",
            "password": "secret123",
        },
        "name": "My Shop",
        "location": "Lusaka",
        "category": "Grocery",
        "affiliate_code": "AFF-123",
    }

    r = client.post("/business/register", json=payload)
    assert r.status_code == 201
    body = r.json()
    business_id = body["business"]["id"]
    assert body["msme_code"].startswith("MSME-")

    by_phone = client.get("/business/phone/+260700000010")
    assert by_phone.status_code == 200
    assert by_phone.json()["id"] == business_id

    sub = client.post(f"/business/{business_id}/subscribe", json={"plan": "paid"})
    assert sub.status_code == 201

    paid_until = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    evt = client.post(
        "/events/payment_success",
        json={"event_id": "evt-1", "business_id": business_id, "plan": "paid", "paid_until": paid_until},
    )
    assert evt.status_code == 200

    status = client.get(f"/business/{business_id}/subscription")
    assert status.status_code == 200
    assert status.json()["status"] == "active"

    events = client.get(f"/events/business/{business_id}")
    assert events.status_code == 200
    assert any(e["event_type"] == "payment_success" for e in events.json())
