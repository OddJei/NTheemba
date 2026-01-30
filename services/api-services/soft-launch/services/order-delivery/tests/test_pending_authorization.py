from __future__ import annotations

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


client = TestClient(app)

VALID_BUSINESS_ID = "biz-123"
OTHER_BUSINESS_ID = "biz-999"


def auth_headers_for_business(business_id: str, role: str | None = None):
    headers = {"Authorization": "Bearer dummy-token", "X-Business-Id": business_id}
    if role:
        headers["X-Role"] = role
    return headers


def test_list_pending_orders_allows_business_owner():
    headers = auth_headers_for_business(VALID_BUSINESS_ID)
    r = client.get("/orders/pending", params={"business_id": VALID_BUSINESS_ID}, headers=headers)
    assert r.status_code == 200


def test_list_pending_deliveries_allows_business_owner():
    headers = auth_headers_for_business(VALID_BUSINESS_ID)
    r = client.get("/deliveries/pending", params={"business_id": VALID_BUSINESS_ID}, headers=headers)
    assert r.status_code == 200


def test_list_pending_orders_forbidden_for_other_business():
    headers = auth_headers_for_business(OTHER_BUSINESS_ID)
    r = client.get("/orders/pending", params={"business_id": VALID_BUSINESS_ID}, headers=headers)
    assert r.status_code == 403


def test_list_pending_deliveries_forbidden_for_other_business():
    headers = auth_headers_for_business(OTHER_BUSINESS_ID)
    r = client.get("/deliveries/pending", params={"business_id": VALID_BUSINESS_ID}, headers=headers)
    assert r.status_code == 403


def test_admin_role_allowed():
    headers = auth_headers_for_business(OTHER_BUSINESS_ID)
    headers["X-Role"] = "admin"
    r = client.get("/orders/pending", params={"business_id": VALID_BUSINESS_ID}, headers=headers)
    assert r.status_code == 200
    r = client.get("/deliveries/pending", params={"business_id": VALID_BUSINESS_ID}, headers=headers)
    assert r.status_code == 200
