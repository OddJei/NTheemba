from __future__ import annotations

import uuid


def test_pawapay_deposit_callback_creates_row_and_can_be_fetched(client, auth_headers):
    deposit_id = str(uuid.uuid4())

    # Callback should not require internal JWT.
    r = client.post(
        "/callbacks/pawapay/deposits",
        json={
            "depositId": deposit_id,
            "status": "COMPLETED",
            "amount": "15.00",
            "currency": "ZMW",
            "country": "ZMB",
            "payer": {"type": "MMO", "accountDetails": {"phoneNumber": "260973456789", "provider": "MTN_MOMO_ZMB"}},
        },
    )
    assert r.status_code == 200

    # Fetching status requires auth.
    g = client.get(f"/pawapay/deposits/{deposit_id}", headers=auth_headers)
    assert g.status_code == 200
    body = g.json()
    assert body["external_id"] == deposit_id
    assert body["status"] == "COMPLETED"
    assert body["currency"] == "ZMW"
    assert body["amount_minor"] == 1500
    # New fields persisted for bookkeeping
    assert "platform_fee_minor" in body
    assert "payment_type" in body


def test_pawapay_initiate_deposit_is_idempotent(client, auth_headers, monkeypatch):
    from src.app import pawapay_client
    from src.app.pawapay_client import PawaPayResponse

    deposit_id = str(uuid.uuid4())

    async def _fake_initiate_deposit(*, deposit_id: str, amount: str, currency: str, phone_number: str, provider: str, correlation_id: str | None):
        return PawaPayResponse(
            status_code=200,
            body={"depositId": deposit_id, "status": "ACCEPTED", "nextStep": "FINAL_STATUS"},
        )

    monkeypatch.setattr(pawapay_client, "initiate_deposit", _fake_initiate_deposit)

    payload = {
        "depositId": deposit_id,
        "order_id": "o1",
        "business_id": "b1",
        "amount_minor": 1500,
        "currency": "ZMW",
        "phoneNumber": "260973456789",
        "provider": "MTN_MOMO_ZMB",
        "paymentType": "one_time",
        "msmeNetMinor": 1200,
    }

    r1 = client.post("/pawapay/deposits/initiate", headers={**auth_headers, "X-Idempotency-Key": "idem-1"}, json=payload)
    assert r1.status_code in (200, 201)
    b1 = r1.json()
    assert b1["external_id"] == deposit_id
    assert b1["status"] == "ACCEPTED"

    # Verify the stored deposit row reflects msme_net and platform fee
    g = client.get(f"/pawapay/deposits/{deposit_id}", headers=auth_headers)
    assert g.status_code == 200
    got = g.json()
    assert got["external_id"] == deposit_id
    assert got.get("platform_fee_minor") == 300
    assert got.get("payment_type") in ("one_time", "one-time", "one_time")

    # Second call with same idempotency key should return same response.
    r2 = client.post("/pawapay/deposits/initiate", headers={**auth_headers, "X-Idempotency-Key": "idem-1"}, json=payload)
    assert r2.status_code in (200, 201)
    b2 = r2.json()
    assert b2["external_id"] == deposit_id
    assert b2["status"] == "ACCEPTED"


def test_pawapay_reconcile_job_updates_stale_deposit(client, auth_headers, monkeypatch):
    from datetime import datetime, timedelta, timezone

    from src.app import pawapay_client
    from src.app.pawapay_client import PawaPayResponse

    deposit_id = str(uuid.uuid4())

    # Create a stale row via callback (this sets updated_at to now).
    r = client.post(
        "/callbacks/pawapay/deposits",
        json={
            "depositId": deposit_id,
            "status": "ACCEPTED",
            "amount": "15.00",
            "currency": "ZMW",
            "payer": {"type": "MMO", "accountDetails": {"phoneNumber": "260973456789", "provider": "MTN_MOMO_ZMB"}},
        },
    )
    assert r.status_code == 200

    # Force it to be stale by directly updating DB timestamps.
    # We do this by calling a private helper via import (simple unit-test approach).
    from sqlalchemy import update

    from src.app.db import SessionLocal
    from src.app.models import PawaPayDeposit

    stale_time = datetime.now(timezone.utc) - timedelta(hours=2)

    async def _make_stale():
        async with SessionLocal() as session:
            await session.execute(
                update(PawaPayDeposit)
                .where(PawaPayDeposit.deposit_id == deposit_id)
                .values(updated_at=stale_time)
            )
            await session.commit()

    import asyncio

    asyncio.run(_make_stale())

    async def _fake_get_deposit_status(*, deposit_id: str, correlation_id: str | None):
        return PawaPayResponse(
            status_code=200,
            body={"depositId": deposit_id, "status": "COMPLETED", "amount": "15.00", "currency": "ZMW"},
        )

    monkeypatch.setattr(pawapay_client, "get_deposit_status", _fake_get_deposit_status)

    # Trigger reconcile.
    jr = client.post("/jobs/pawapay/reconcile", headers=auth_headers)
    assert jr.status_code == 200
    out = jr.json()
    assert out["checked"] >= 1

    g = client.get(f"/pawapay/deposits/{deposit_id}", headers=auth_headers)
    assert g.status_code == 200
    body = g.json()
    assert body["status"] == "COMPLETED"
