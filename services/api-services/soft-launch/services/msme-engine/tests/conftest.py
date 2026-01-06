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
    tmp = tempfile.NamedTemporaryFile(prefix="msme_engine_test_", suffix=".db", delete=False)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp.name}"
    os.environ["MSME_JWT_SECRET"] = "test-secret"

    # Ensure `src` package is importable.
    sys.path.insert(0, str(service_root))


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture()
def client() -> TestClient:
    from src.app.main import app

    with TestClient(app) as c:
        yield c
