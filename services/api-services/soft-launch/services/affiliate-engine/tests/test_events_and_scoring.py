from __future__ import annotations

from datetime import datetime, timezone
import uuid


def _uuid() -> str:
    return str(uuid.uuid4())


def _create_affiliate(client, name: str, phone: str) -> str:
    resp = client.post(
        "/affiliates",
        headers={"X-Idempotency-Key": f"create-{name}", "X-Correlation-Id": f"corr-{name}"},
        json={"name": name, "phone": phone},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def test_order_delivered_records_event_and_snapshot(client) -> None:
    a_id = _create_affiliate(client, "OD", "+260900001001")

    order_id = _uuid()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    payload = {
        "event_id": _uuid(),
        "order_id": order_id,
        "affiliate_id": a_id,
        "occurred_at": now,
        "producer": "order-delivery",
        "amount_zmw": 25.0,
        "user_phone": "+260811234567",
    }

    resp = client.post("/events/order/delivered", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("attribution_created") in (True, False)

    events = client.get(f"/events/affiliate/{a_id}").json()
    assert any(e.get("order_id") == order_id and e.get("event_type") == "sale" for e in events)

    standings = client.get("/pool/standings").json()["standings"]
    by_aff = {r["affiliate_id"]: r for r in standings}
    assert a_id in by_aff
    assert by_aff[a_id]["sales_volume"] >= 25.0


def test_msme_referral_records_and_snapshot(client, monkeypatch) -> None:
    a_id = _create_affiliate(client, "MR", "+260900001011")

    deposit_id = _uuid()
    # Fake deposit returned by payment-revenue
    fake_deposit = {
        "payment_id": _uuid(),
        "depositId": deposit_id,
        "business_id": _uuid(),
        "status": "completed",
        "amount": 150.0,
    }

    class FakeResp:
        def __init__(self, payload):
            self._p = payload
            self.status_code = 200

        def json(self):
            return self._p

    async def fake_get(self, url, headers=None, timeout=None):
        return FakeResp(fake_deposit)

    monkeypatch.setattr("httpx.AsyncClient.get", fake_get)

    payload = {"deposit_id": deposit_id, "affiliate_id": a_id, "business_id": fake_deposit["business_id"]}
    resp = client.post("/events/msme/referral", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("recorded") is True

    standings = client.get("/pool/standings").json()["standings"]
    by_aff = {r["affiliate_id"]: r for r in standings}
    assert a_id in by_aff
    # msme_referrals should be incremented for a first-ever business
    assert by_aff[a_id]["msme_referrals"] >= 1


def test_session_cycle_increments_snapshot(client) -> None:
    a_id = _create_affiliate(client, "SC", "+260900001021")

    payload = {
        "event_id": _uuid(),
        "affiliate_id": a_id,
        "producer": "session-service",
        "session_id": _uuid(),
        "cycle_id": _uuid(),
        "cycle_state": "created",
        "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    resp = client.post("/events/session-cycle-created", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "ok"

    standings = client.get("/pool/standings").json()["standings"]
    by_aff = {r["affiliate_id"]: r for r in standings}
    assert a_id in by_aff
    assert by_aff[a_id]["session_cycles"] >= 1
