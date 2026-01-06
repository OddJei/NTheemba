from __future__ import annotations

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


def _create_link(client, affiliate_id: str, code: str) -> None:
    resp = client.post(
        f"/affiliates/{affiliate_id}/links",
        headers={"X-Idempotency-Key": f"link-{affiliate_id}-{code}", "X-Correlation-Id": f"corr-link-{code}"},
        json={"code": code, "campaign": "camp"},
    )
    assert resp.status_code == 200


def _track_click(client, affiliate_code: str, session_id: str, user_phone: str) -> str:
    event_id = _uuid()
    resp = client.post(
        "/track/click",
        headers={"X-Idempotency-Key": event_id, "X-Correlation-Id": f"corr-click-{session_id}"},
        json={"event_id": event_id, "affiliate_code": affiliate_code, "session_id": session_id, "user_phone": user_phone},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def _attribute_order(client, affiliate_code: str, order_id: str, business_id: str, session_id: str, user_phone: str) -> None:
    event_id = _uuid()
    resp = client.post(
        "/attribute/order",
        headers={"X-Idempotency-Key": event_id, "X-Correlation-Id": f"corr-attr-{order_id}"},
        json={
            "event_id": event_id,
            "affiliate_code": affiliate_code,
            "order_id": order_id,
            "business_id": business_id,
            "session_id": session_id,
            "user_phone": user_phone,
        },
    )
    assert resp.status_code == 200


def test_clicks_are_unique_phones_in_pool_standings(client) -> None:
    a_id = _create_affiliate(client, "U", "+260900000031")
    _create_link(client, a_id, "codeU")

    phone = "+260811000123"
    _track_click(client, "codeU", _uuid(), phone)
    _track_click(client, "codeU", _uuid(), phone)  # same phone again should not increase clicks

    rows = client.get("/pool/standings").json()["standings"]
    by_aff = {r["affiliate_id"]: r for r in rows}
    assert by_aff[a_id]["clicks"] == 1


def test_affiliate_events_audit_trail(client) -> None:
    a_id = _create_affiliate(client, "E", "+260900000041")
    _create_link(client, a_id, "codeE")

    phone = "+260811000555"
    _track_click(client, "codeE", _uuid(), phone)

    events = client.get(f"/events/affiliate/{a_id}").json()
    assert isinstance(events, list)
    assert any(e["event_type"] == "campaign_click" for e in events)


def _payment_success(client, order_id: str, business_id: str, user_phone: str, affiliate_amount: float) -> None:
    payload = {
        "event_id": _uuid(),
        "event_type": "payment_success",
        "occurred_at": "2026-01-05T00:00:00Z",
        "correlation_id": _uuid(),
        "producer": "payment-revenue",
        "payment_id": _uuid(),
        "order_id": order_id,
        "business_id": business_id,
        "user_phone": user_phone,
        "amount": affiliate_amount * 10,
        "currency": "ZMW",
        "earnings": {
            "msme_amount": affiliate_amount * 8,
            "affiliate_amount": affiliate_amount,
            "platform_amount": affiliate_amount,
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


def _get_open_epoch_id(client) -> str:
    resp = client.get("/admin/epochs", headers={"X-Admin-Key": "test-admin"})
    assert resp.status_code == 200
    epochs = resp.json()
    open_epochs = [e for e in epochs if e["status"] == "open"]
    assert open_epochs
    return open_epochs[0]["id"]


def test_pool_allocations_sum_to_pool_and_rankings(client) -> None:
    # Two affiliates: A performs better than B.
    a_id = _create_affiliate(client, "A", "+260900000010")
    b_id = _create_affiliate(client, "B", "+260900000020")

    _create_link(client, a_id, "codeA")
    _create_link(client, b_id, "codeB")

    # A: 2 paid orders, 2 unique buyers, 2 MSMEs
    for i in range(2):
        session_id = _uuid()
        buyer_phone = f"+26081100000{i}"
        business_id = _uuid()
        order_id = _uuid()
        _track_click(client, "codeA", session_id, buyer_phone)
        _attribute_order(client, "codeA", order_id, business_id, session_id, buyer_phone)
        _payment_success(client, order_id, business_id, buyer_phone, affiliate_amount=10.0)

    # B: 1 paid order, 1 buyer, 1 MSME
    session_id = _uuid()
    buyer_phone = "+260811000009"
    business_id = _uuid()
    order_id = _uuid()
    _track_click(client, "codeB", session_id, buyer_phone)
    _attribute_order(client, "codeB", order_id, business_id, session_id, buyer_phone)
    _payment_success(client, order_id, business_id, buyer_phone, affiliate_amount=10.0)

    # Set gross revenue so pool is deterministic.
    epoch_id = _get_open_epoch_id(client)
    resp = client.put(
        f"/admin/epochs/{epoch_id}/gross-revenue",
        headers={"X-Admin-Key": "test-admin"},
        json={"gross_revenue_zmw": 1000.0},
    )
    assert resp.status_code == 200
    assert resp.json()["pool_pct"] == 0.10

    # Standings should be sorted by projected payout.
    standings = client.get("/pool/standings").json()
    assert standings["pool_amount_zmw"] == 100.0
    rows = standings["standings"]
    assert rows
    assert rows[0]["projected_payout_zmw"] >= rows[-1]["projected_payout_zmw"]

    # Close epoch and check allocations sum to pool.
    allocations = client.post(
        f"/admin/epochs/{epoch_id}/close",
        headers={"X-Admin-Key": "test-admin"},
    ).json()

    total_payout = sum(a["payout_zmw"] for a in allocations)
    assert abs(total_payout - 100.0) < 0.0001

    by_aff = {a["affiliate_id"]: a["payout_zmw"] for a in allocations}
    assert by_aff[a_id] > by_aff[b_id]


def test_tier_multiplier_increases_share(client) -> None:
    # Create two affiliates with identical performance but B has gold tier.
    a_id = _create_affiliate(client, "A2", "+260900000011")
    b_id = _create_affiliate(client, "B2", "+260900000021")

    _create_link(client, a_id, "codeA2")
    _create_link(client, b_id, "codeB2")

    # Assign gold to B2
    resp = client.put(
        f"/admin/affiliates/{b_id}/tier",
        headers={"X-Admin-Key": "test-admin"},
        json={"tier_name": "gold"},
    )
    assert resp.status_code == 200

    # Same single paid order for each
    for code in ("codeA2", "codeB2"):
        session_id = _uuid()
        buyer_phone = f"+260822{session_id[-6:]}"
        business_id = _uuid()
        order_id = _uuid()
        _track_click(client, code, session_id, buyer_phone)
        _attribute_order(client, code, order_id, business_id, session_id, buyer_phone)
        _payment_success(client, order_id, business_id, buyer_phone, affiliate_amount=10.0)

    epoch_id = _get_open_epoch_id(client)
    client.put(
        f"/admin/epochs/{epoch_id}/gross-revenue",
        headers={"X-Admin-Key": "test-admin"},
        json={"gross_revenue_zmw": 1000.0},
    )

    standings = client.get("/pool/standings").json()["standings"]
    by_aff = {s["affiliate_id"]: s for s in standings}

    # Gold tier should increase B2 projected payout over A2 with equal underlying performance.
    assert by_aff[b_id]["tier_name"] == "gold"
    assert by_aff[b_id]["projected_payout_zmw"] > by_aff[a_id]["projected_payout_zmw"]
