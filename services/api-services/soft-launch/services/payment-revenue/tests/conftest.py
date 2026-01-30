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
_db_file = Path(tempfile.gettempdir()) / f"payment_revenue_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_file.as_posix()}"

# Make affiliate commission non-zero in tests.
os.environ.setdefault("AFFILIATE_COMMISSION_SHARE", "1.0")


@pytest.fixture()
def client() -> TestClient:
    from src.app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    # Most endpoints are protected by auth middleware; use the test shortcut.
    # Admin role bypasses business scoping checks in unit tests.
    return {"Authorization": "Bearer dummy-token", "X-Role": "admin"}
