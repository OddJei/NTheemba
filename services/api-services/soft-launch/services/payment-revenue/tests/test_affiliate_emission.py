from __future__ import annotations

import uuid

import pytest


def test_payment_success_emits_affiliate_engine_payload_contains_affiliate_code(client, monkeypatch):
    from src.app import main as pr_main
    from fastapi import HTTPException

    calls: list[dict] = []
    fail_first = {"done": False}

    async def _noop_dispatch_to_order_delivery(*, order_id: str, correlation_id: str) -> None:
        return None

    async def _noop_notify(*, user_id, business_id, template, payload, correlation_id) -> None:
        return None

    async def _dispatch_to_affiliate_engine(*, payload: dict, correlation_id: str) -> None:
        # Simulate a transient failure on the first attempt so we can assert retry behavior.
        calls.append({"payload": payload, "correlation_id": correlation_id})
        if not fail_first["done"]:
            fail_first["done"] = True
            raise HTTPException(status_code=502, detail="simulated_affiliate_engine_down")

    monkeypatch.setattr(pr_main, "_dispatch_to_order_delivery", _noop_dispatch_to_order_delivery)
    monkeypatch.setattr(pr_main, "_notify_in_app", _noop_notify)
    monkeypatch.setattr(pr_main, "_dispatch_to_affiliate_engine", _dispatch_to_affiliate_engine)

    order_id = str(uuid.uuid4())

    # First call: settlement is created but dispatch fails.
    r1 = client.post(
        "/events/payment-success",
        headers={"X-Correlation-Id": "corr-pay-1"},
        json={
            "order_id": order_id,
            "payment_id": str(uuid.uuid4()),
            "business_id": str(uuid.uuid4()),
            "user_phone": "+260971000000",
            "currency": "ZMW",
            "amount_minor": 10000,
            "metadata": {"affiliate_code": "aff-code-123"},
        },
    )
    assert r1.status_code == 502

    # Second call: should retry and succeed (handler returns existing settlement).
    r2 = client.post(
        "/events/payment-success",
        headers={"X-Correlation-Id": "corr-pay-2"},
        json={
            "order_id": order_id,
            "payment_id": str(uuid.uuid4()),
            "business_id": str(uuid.uuid4()),
            "user_phone": "+260971000000",
            "currency": "ZMW",
            "amount_minor": 10000,
            "metadata": {"affiliate_code": "aff-code-123"},
        },
    )
    assert r2.status_code == 200

    # We should have attempted affiliate dispatch twice.
    assert len(calls) >= 2

    last = calls[-1]["payload"]
    assert last["event_type"] == "payment_success"
    assert last["producer"] == "payment-revenue"
    assert last["order_id"] == order_id
    assert last["earnings"]["affiliate_code"] == "aff-code-123"
    assert isinstance(last["earnings"]["affiliate_amount"], float)
