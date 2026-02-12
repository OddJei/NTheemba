import os
import sys
from pathlib import Path
import pytest
from httpx import AsyncClient

# Ensure service package is importable and test-specific env vars are set early.
SERVICE_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("OUTBOX_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./ice_test.db")
sys.path.insert(0, str(SERVICE_DIR))

# Ensure top-level `src` package resolves to the service `src` directory for imports like `from src.app...`.
import types
src_pkg = types.ModuleType("src")
src_pkg.__path__ = [str(SERVICE_DIR / "src")]
sys.modules["src"] = src_pkg

from src.app.main import app, create_tables


@pytest.mark.asyncio
async def test_session_confirm_creates_outbox():
    headers = {"X-Internal-Secret": os.environ.get("OUTBOX_INTERNAL_SECRET")}
    payload = {"order_id": "order-123", "affiliate_id": "aff-1", "amount_minor": 12345, "idempotency_key": "evt-1"}

    # Ensure tables exist (call startup table-creation directly for tests).
    await create_tables()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post(f"/sessions/session-1/confirm", json=payload, headers=headers)

    assert r.status_code == 200
    body = r.json()
    assert "outbox_id" in body

    # cleanup DB file created by test (best-effort)
    dbfile = Path(SERVICE_DIR) / "ice_test.db"
    try:
        if dbfile.exists():
            dbfile.unlink()
    except Exception:
        pass
