from __future__ import annotations

from datetime import datetime, timezone
import uuid


def _uuid() -> str:
    return str(uuid.uuid4())


def test_payment_success_creates_no_earnings(client) -> None:
    # create affiliate
    resp = client.post(
        "/affiliates",
        headers={"X-Idempotency-Key": f"create-test", "X-Correlation-Id": "corr-test"},
        json={"name": "NoPay", "phone": "+260900000099"},
    )
    assert resp.status_code == 200
    affiliate_id = resp.json()["id"]

    # create link
    resp = client.post(
        f"/affiliates/{affiliate_id}/links",
        headers={"X-Idempotency-Key": "link-test", "X-Correlation-Id": "corr-link"},
        json={"code": "nopay", "campaign": "camp", "product_id": _uuid(), "business_id": _uuid()},
    )
    assert resp.status_code == 200

    # attribute an order
    order_id = _uuid()
    session_id = _uuid()
    buyer_phone = "+260811000888"
    business_id = _uuid()

    event_id = _uuid()
    resp = client.post(
        "/track/click",
        headers={"X-Idempotency-Key": _uuid(), "X-Correlation-Id": "corr-click"},
        json={"event_id": _uuid(), "affiliate_code": "nopay", "session_id": session_id, "user_phone": buyer_phone},
    )
    assert resp.status_code == 200

    event_id = _uuid()
    resp = client.post(
        "/attribute/order",
        headers={"X-Idempotency-Key": event_id, "X-Correlation-Id": "corr-attr"},
        json={
            "event_id": event_id,
            "affiliate_code": "nopay",
            "order_id": order_id,
            "business_id": business_id,
            "session_id": session_id,
            "user_phone": buyer_phone,
        },
    )
    assert resp.status_code == 200

    # send payment-success event
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "event_id": _uuid(),
        "event_type": "payment_success",
        "occurred_at": now,
        "correlation_id": _uuid(),
        "producer": "payment-revenue",
        "payment_id": _uuid(),
        "order_id": order_id,
        "business_id": business_id,
        "user_phone": buyer_phone,
        "amount": 100.0,
        "currency": "ZMW",
        "earnings": {
            "msme_amount": 80.0,
            "affiliate_amount": 10.0,
            "platform_amount": 10.0,
            "affiliate_id": None,
            "affiliate_code": None,
        },
    }

    resp = client.post(
        "/events/payment-success",
        headers={"X-Idempotency-Key": payload["event_id"], "X-Correlation-Id": payload["correlation_id"]},
        json=payload,
    )
    assert resp.status_code == 200

    # earnings summary and records should be empty / zero for the affiliate
    summary = client.get(f"/affiliates/{affiliate_id}/earnings").json()
    assert summary["total_amount"] == 0.0
    records = client.get(f"/affiliates/{affiliate_id}/earnings/records").json()
    assert isinstance(records, list)
    assert len(records) == 0
