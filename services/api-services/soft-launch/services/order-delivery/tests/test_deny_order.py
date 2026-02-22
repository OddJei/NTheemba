import os
import sys
import tempfile
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

# Ensure we can import `src.app.*` when running tests from repo root or service dir.
SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

# Use a unique DB per test run to avoid state leakage.
_db_file = Path(tempfile.gettempdir()) / f"order_delivery_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_file.as_posix()}"

from src.app import main as od_main


def auth_headers_for_business(business_id: str):
    return {"Authorization": "Bearer dummy-token", "X-Business-Id": business_id}


def test_deny_unpaid_order_no_refund():
    with TestClient(od_main.app) as client:
        headers = auth_headers_for_business("biz-deny-1")

        # create unpaid order (pending_payment)
        r = client.post(
            "/orders/create",
            headers=headers,
            json={
                "session_id": None,
                "user_phone": "+260971000000",
                "user_id": None,
                "business_id": "biz-deny-1",
                "delivery_method": "pickup",
                "total_amount": 500,
                "currency": "ZMW",
                "metadata": {"source": "test"},
            },
        )
        assert r.status_code in (200, 201)
        order_id = r.json()["id"]

        # deny the unpaid order
        r = client.post(f"/orders/{order_id}/deny", headers=headers, json={"reason": "customer_canceled", "initiate_refund": True})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "denied"
        meta = body.get("metadata") or {}
        # unpaid -> no refund recorded
        assert meta.get("refund") is None


def test_deny_paid_order_records_refund():
    with TestClient(od_main.app) as client:
        headers = auth_headers_for_business("biz-deny-2")

        # create order and mark paid
        r = client.post(
            "/orders/create",
            headers=headers,
            json={
                "session_id": None,
                "user_phone": "+260971000001",
                "user_id": None,
                "business_id": "biz-deny-2",
                "delivery_method": "pickup",
                "total_amount": 1000,
                "currency": "ZMW",
                "metadata": {"source": "test"},
            },
        )
        assert r.status_code in (200, 201)
        order_id = r.json()["id"]

        r = client.post(f"/orders/{order_id}/mark_paid", headers=headers)
        assert r.status_code == 200

        # deny the paid order and request refund
        r = client.post(f"/orders/{order_id}/deny", headers=headers, json={"reason": "not_delivered", "initiate_refund": True})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "denied"
        meta = body.get("metadata") or {}
        refund = meta.get("refund")
        assert isinstance(refund, dict)
        assert refund.get("status") == "requested"
        assert refund.get("reason") in ("not_delivered", "denied_by_business")


def test_deny_forbidden_for_other_business():
    with TestClient(od_main.app) as client:
        # create order under biz-A
        headers = auth_headers_for_business("biz-A")
        r = client.post(
            "/orders/create",
            headers=headers,
            json={
                "session_id": None,
                "user_phone": "+260971000002",
                "user_id": None,
                "business_id": "biz-A",
                "delivery_method": "pickup",
                "total_amount": 200,
                "currency": "ZMW",
                "metadata": {},
            },
        )
        assert r.status_code in (200, 201)
        order_id = r.json()["id"]

        # attempt to deny as biz-B owner
        headers_b = auth_headers_for_business("biz-B")
        r = client.post(f"/orders/{order_id}/deny", headers=headers_b, json={})
        assert r.status_code == 403
