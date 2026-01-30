from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# Ensure we can import `src.app.*` when running tests from repo root or service dir.
SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

# Use a unique DB per test run to avoid state leakage.
_db_file = Path(tempfile.gettempdir()) / f"order_delivery_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_file.as_posix()}"

from src.app import main as od_main


@pytest.mark.asyncio
async def test_order_create_emits_order_created_to_affiliate_engine(monkeypatch):
    captured: dict = {}

    async def _fake_fee(*, business_id: str):
        return 700, "test"

    async def _fake_dispatch(*, payload: dict, correlation_id: str) -> bool:
        captured["payload"] = payload
        captured["correlation_id"] = correlation_id
        return True

    monkeypatch.setattr(od_main, "_get_transaction_fee_bps_for_business", _fake_fee)
    monkeypatch.setattr(od_main, "_dispatch_to_affiliate_engine_order_created", _fake_dispatch)

    with TestClient(od_main.app) as client:
        r = client.post(
            "/orders/create",
            headers={"X-Correlation-Id": "corr-aff-1", "Authorization": "Bearer dummy-token"},
            json={
                "session_id": None,
                "user_phone": "+260971000000",
                "user_id": None,
                "business_id": str(uuid.uuid4()),
                "delivery_method": "pickup",
                "total_amount": 100,
                "currency": "ZMW",
                "metadata": {"affiliate_code": "aff-code-123"},
            },
        )

    assert r.status_code in (200, 201)
    assert captured["correlation_id"] == "corr-aff-1"

    payload = captured["payload"]
    assert payload["event_type"] == "order_created"
    assert payload["producer"] == "order-delivery"
    assert payload["affiliate_code"] == "aff-code-123"
    assert payload["order_id"]
    assert payload["business_id"]
    assert payload["occurred_at"].endswith("Z")
