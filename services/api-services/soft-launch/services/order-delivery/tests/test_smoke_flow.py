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

from src.app.main import app


def test_order_paid_delivery_confirm_flow():
    with TestClient(app) as client:
        auth = {"Authorization": "Bearer dummy-token"}
        user_phone = f"+260700{uuid.uuid4().hex[:9]}"

        # Create order
        r = client.post(
            "/orders/create",
            headers=auth,
            json={
                "session_id": None,
                "user_phone": user_phone,
                "user_id": None,
                "business_id": str(uuid.uuid4()),
                "delivery_method": "pickup",
                "total_amount": 100,
                "currency": "ZAR",
                "metadata": {"source": "test"},
            },
        )
        assert r.status_code in (200, 201)
        order_id = r.json()["id"]

        # Mark paid
        r = client.post(f"/orders/{order_id}/mark_paid", headers=auth)
        assert r.status_code == 200
        assert r.json()["status"] in ("paid", "delivered")

        # Initiate delivery (generate code)
        r = client.post(f"/delivery/initiate/{order_id}", headers=auth)
        assert r.status_code in (200, 201)
        payload = r.json()
        delivery_id = payload["delivery"]["id"]
        delivery_code = payload["delivery_code"]
        assert isinstance(delivery_code, str)
        assert len(delivery_code) == 6

        # Confirm delivery
        r = client.post(
            f"/delivery/{delivery_id}/confirm",
            headers=auth,
            json={"delivery_code": delivery_code, "confirmed_by": "test"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "confirmed"

        # Order should be delivered
        r = client.get(f"/orders/{order_id}", headers=auth)
        assert r.status_code == 200
        assert r.json()["status"] == "delivered"
