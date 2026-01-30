from __future__ import annotations

import uuid

import pytest


def test_refund_request_requires_settlement(client):
    r = client.post(
        "/refunds/request",
        headers={"Authorization": "Bearer dummy-token", "X-Business-Id": "biz-1"},
        json={"order_id": str(uuid.uuid4()), "reason": "no_delivery"},
    )
    assert r.status_code == 404


def test_refund_request_blocks_when_delivery_confirmed(client, monkeypatch):
    from src.app import main as pr_main

    async def _noop_dispatch_to_order_delivery(*, order_id: str, correlation_id: str) -> None:
        return None

    async def _noop_dispatch_to_affiliate_engine(*, payload: dict, correlation_id: str) -> None:
        return None

    async def _fee(*args, **kwargs):
        return 500, "test"

    async def _confirmed(*, order_id: str, authorization: str | None, correlation_id: str | None) -> bool:
        return True

    monkeypatch.setattr(pr_main, "delivery_is_confirmed", _confirmed)
    monkeypatch.setattr(pr_main, "_dispatch_to_order_delivery", _noop_dispatch_to_order_delivery)
    monkeypatch.setattr(pr_main, "_dispatch_to_affiliate_engine", _noop_dispatch_to_affiliate_engine)
    monkeypatch.setattr(pr_main, "_get_fee_bps_for_business", _fee)

    # Create a settlement by calling payment-success
    order_id = str(uuid.uuid4())
    r = client.post(
        "/events/payment-success",
        headers={"X-Correlation-Id": "corr-1", "Authorization": "Bearer dummy-token", "X-Business-Id": "biz-1"},
        json={
            "order_id": order_id,
            "payment_id": str(uuid.uuid4()),
            "business_id": "biz-1",
            "user_phone": "+260971000000",
            "currency": "ZMW",
            "amount_minor": 10000,
            "metadata": {},
        },
    )
    assert r.status_code in (200, 201, 502)

    r2 = client.post(
        "/refunds/request",
        headers={"Authorization": "Bearer dummy-token", "X-Business-Id": "biz-1"},
        json={"order_id": order_id, "reason": "not_delivered"},
    )
    assert r2.status_code == 409


def test_refund_request_succeeds_when_not_confirmed(client, monkeypatch):
    from src.app import main as pr_main

    async def _noop_dispatch_to_order_delivery(*, order_id: str, correlation_id: str) -> None:
        return None

    async def _noop_dispatch_to_affiliate_engine(*, payload: dict, correlation_id: str) -> None:
        return None

    async def _fee(*args, **kwargs):
        return 500, "test"

    async def _not_confirmed(*, order_id: str, authorization: str | None, correlation_id: str | None) -> bool:
        return False

    async def _noop_notify(*, user_id, business_id, template, payload, correlation_id):
        return None

    monkeypatch.setattr(pr_main, "delivery_is_confirmed", _not_confirmed)
    monkeypatch.setattr(pr_main, "_notify_in_app", _noop_notify)
    monkeypatch.setattr(pr_main, "_dispatch_to_order_delivery", _noop_dispatch_to_order_delivery)
    monkeypatch.setattr(pr_main, "_dispatch_to_affiliate_engine", _noop_dispatch_to_affiliate_engine)
    monkeypatch.setattr(pr_main, "_get_fee_bps_for_business", _fee)

    order_id = str(uuid.uuid4())
    r = client.post(
        "/events/payment-success",
        headers={"X-Correlation-Id": "corr-2", "Authorization": "Bearer dummy-token", "X-Business-Id": "biz-1"},
        json={
            "order_id": order_id,
            "payment_id": str(uuid.uuid4()),
            "business_id": "biz-1",
            "user_phone": "+260971000000",
            "currency": "ZMW",
            "amount_minor": 10000,
            "metadata": {},
        },
    )
    assert r.status_code in (200, 201, 502)

    r2 = client.post(
        "/refunds/request",
        headers={"Authorization": "Bearer dummy-token", "X-Business-Id": "biz-1"},
        json={"order_id": order_id, "reason": "not_confirmed"},
    )
    assert r2.status_code in (200, 201)
    body = r2.json()
    assert body["order_id"] == order_id
    assert body["business_id"] == "biz-1"
    assert body["status"] in ("refund_requested", "refund_already_requested")
