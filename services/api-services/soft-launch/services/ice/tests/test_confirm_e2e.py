import os
import sys
from pathlib import Path
import pytest
from httpx import AsyncClient
import types

SERVICE_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("OUTBOX_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./ice_test.db")
sys.path.insert(0, str(SERVICE_DIR))

src_pkg = types.ModuleType("src")
src_pkg.__path__ = [str(SERVICE_DIR / "src")]
sys.modules["src"] = src_pkg

from src.app.main import app, create_tables


@pytest.mark.asyncio
async def test_confirm_then_fetch_pending():
    headers = {"X-Internal-Secret": os.environ.get("OUTBOX_INTERNAL_SECRET")}
    payload = {"order_id": "order-e2e", "affiliate_id": None, "amount_minor": 5000, "idempotency_key": "evt-e2e"}

    # Ensure DB tables
    await create_tables()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post(f"/sessions/e2e-session/confirm", json=payload, headers=headers)
        assert r.status_code == 200
        outbox_id = r.json().get("outbox_id")

        # Now fetch pending outbox rows and assert our event is present
        r2 = await ac.get("/outbox/pending", headers=headers)
        assert r2.status_code == 200
        rows = r2.json()
        assert any((row.get("event_type") == "ice.confirmed" or row.get("event_type") == "ice.confirmed") for row in rows)

    # cleanup sqlite test DB (best-effort)
    dbfile = Path(SERVICE_DIR) / "ice_test.db"
    try:
        if dbfile.exists():
            dbfile.unlink()
    except Exception:
        pass
