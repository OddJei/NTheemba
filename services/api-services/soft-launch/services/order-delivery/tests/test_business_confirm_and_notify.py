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
async def test_customer_confirm_notifies_business(monkeypatch):
    calls = []

    async def _fake_notify(*, user_id, business_id, template, payload, correlation_id):
        calls.append({"user_id": user_id, "business_id": business_id, "template": template, "payload": payload})

    monkeypatch.setattr(od_main, "_notify_in_app", _fake_notify)

    with TestClient(od_main.app) as client:
        auth = {"Authorization": "Bearer dummy-token"}
        biz = str(uuid.uuid4())

        r = client.post(
            "/orders/create",
            headers=auth,
            json={
                "session_id": None,
                "user_phone": "+260971000000",
                "user_id": None,
                "business_id": biz,
                "delivery_method": "pickup",
                "total_amount": 100,
                "currency": "ZAR",
                "metadata": {"source": "test"},
            },
        )
        assert r.status_code in (200, 201)
        order_id = r.json()["id"]

        r = client.post(f"/orders/{order_id}/mark_paid", headers=auth)
        assert r.status_code == 200

        r = client.post(f"/delivery/initiate/{order_id}", headers=auth)
        assert r.status_code in (200, 201)
        delivery_id = r.json()["delivery"]["id"]
        delivery_code = r.json()["delivery_code"]

        r = client.post(
            f"/delivery/{delivery_id}/confirm",
            headers=auth,
            json={"delivery_code": delivery_code, "confirmed_by": "test"},
        )
        assert r.status_code == 200

    templates = [c["template"] for c in calls]
    assert "delivery_confirmed" in templates
    assert "delivery_confirmed_business" in templates


def test_business_can_confirm_order_and_meta_updated():
    with TestClient(od_main.app) as client:
        auth = {"Authorization": "Bearer dummy-token", "X-Business-Id": "biz-123"}

        r = client.post(
            "/orders/create",
            headers=auth,
            json={
                "session_id": None,
                "user_phone": "+260971000000",
                "user_id": None,
                "business_id": "biz-123",
                "delivery_method": "pickup",
                "total_amount": 100,
                "currency": "ZAR",
                "metadata": {"source": "test"},
            },
        )
        assert r.status_code in (200, 201)
        order_id = r.json()["id"]

        r = client.post(f"/orders/{order_id}/confirm", headers=auth, json={"confirmed_by": "owner"})
        assert r.status_code == 200
        meta = r.json().get("metadata") or {}
        assert "msme_confirmed_at" in meta
        assert meta.get("msme_confirmed_by") in ("owner", None)
