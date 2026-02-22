import pytest

# Integration-style test template for platform-fee flow.
# This is a scaffold showing the sequence to test:
# 1) create a deposit (or simulate pawapay deposit callback)
# 2) ensure deposit persisted without a PlatformFee
# 3) emit delivery event to /events/order-delivered
# 4) assert a PlatformFee row is created exactly once
# 5) simulate a refund and assert refund.platform_fee_minor is persisted
#
# Fill in fixtures for `client` (httpx AsyncClient against test app) and
# `db` (async session) according to your project's test harness.

@pytest.mark.asyncio
async def test_deposit_delivery_creates_platform_fee(client, db):
    # Arrange: create deposit via API or by inserting a PawaPayDeposit row
    # TODO: implement deposit creation using your project's fixtures
    deposit = {
        "deposit_id": "test-dep-1",
        "order_id": "order-123",
        "amount_minor": 10000,
        "currency": "ZMW",
    }

    # Act: simulate delivery event
    resp = await client.post(
        "/events/order-delivered",
        json={"order_id": deposit["order_id"], "deposit_id": deposit["deposit_id"], "platform_fee_minor": 500},
        headers={"X-Idempotency-Key": "test-order-delivered-1"},
    )

    # Assert: status and payload expectations
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body.get("ok") is True

    # TODO: query DB to assert PlatformFee exists and only one row created.
    # Example (pseudo):
    # pf = await db.fetch_one("SELECT * FROM platform_fees WHERE order_id = $1", [deposit['order_id']])
    # assert pf and int(pf['amount_minor']) == 500


@pytest.mark.asyncio
async def test_refund_persists_platform_fee_on_refund(client, db):
    # Arrange: ensure deposit and platform_fee exist (could reuse fixtures)
    # TODO: implement scenario and simulate pawapay refund callback

    # Act: call refund callback endpoint
    # resp = await client.post("/callbacks/pawapay/refunds", json={...})

    # Assert: refund row includes `platform_fee_minor` and gross revenue adjustments apply
    # TODO: query DB for PawaPayRefund and assert `platform_fee_minor` > 0
    pass
