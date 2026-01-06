from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def service_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _configure_test_db(service_root: Path) -> None:
    # Configure DB once per test session BEFORE importing app modules.
    tmp = tempfile.NamedTemporaryFile(prefix="affiliate_engine_test_", suffix=".db", delete=False)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp.name}"

    # Admin endpoints auth.
    os.environ["AFFILIATE_ADMIN_KEY"] = "test-admin"

    # Ensure `src` package is importable.
    sys.path.insert(0, str(service_root))


@pytest.fixture()
def client() -> TestClient:
    from src.app.main import app

    with TestClient(app) as test_client:
        yield test_client
