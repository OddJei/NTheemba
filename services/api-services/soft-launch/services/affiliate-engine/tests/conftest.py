from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# Pytest imports test modules during collection. Some tests import `src.app.*` at
# module import time, so we must ensure the service root is on `sys.path` and
# required env vars are set before collection completes.
_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVICE_ROOT))

if "DATABASE_URL" not in os.environ:
    tmp = tempfile.NamedTemporaryFile(prefix="affiliate_engine_test_", suffix=".db", delete=False)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp.name}"

os.environ.setdefault("AFFILIATE_ADMIN_KEY", "test-admin")
os.environ.setdefault("AFFILIATE_SKIP_LINK_TARGET_VALIDATION", "1")
os.environ.setdefault("AFFILIATE_OP_MIN_CLICKS", "1")
os.environ.setdefault("AFFILIATE_OP_MIN_PAID_ATTRIBUTIONS", "1")
os.environ.setdefault("AFFILIATE_OP_MIN_UNIQUE_BUYERS", "1")
os.environ.setdefault("AFFILIATE_OP_MIN_SALES_VOLUME", "0")

# Tests should not rely on external services being up.
os.environ.setdefault("AUDIT_EMIT_ENABLED", "0")


@pytest.fixture(scope="session")
def service_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _configure_test_db(service_root: Path) -> None:
    # Back-compat: configuration is now applied at module import time.
    # Keep this fixture so existing tests relying on it still work.
    return None


@pytest.fixture()
def client() -> TestClient:
    # Drop and recreate all tables for each test to ensure clean state.
    import asyncio
    from src.app.db import Base, engine
    from src.app.main import app

    async def _reset_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_reset_db())

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def anyio_backend() -> str:
    # This service uses asyncio-based drivers (aiosqlite/httpx asyncio), so
    # running anyio tests under trio will fail/hang.
    return "asyncio"
