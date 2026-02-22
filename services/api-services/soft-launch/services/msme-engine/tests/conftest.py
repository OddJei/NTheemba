import os
import sys

# Ensure the package source is on sys.path when pytest runs from repo root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SRC = os.path.join(ROOT, "services", "msme-engine", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# Provide a sensible default DATABASE_URL for local test Postgres started via docker-compose.test.yml
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@127.0.0.1:5433/ntheemba")
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
    # Disable emitting audit events during tests for determinism
    os.environ.setdefault("AUDIT_EMIT_ENABLED", "0")

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
