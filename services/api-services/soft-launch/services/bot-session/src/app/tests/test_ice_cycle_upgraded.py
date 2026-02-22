import os
import sys
import pathlib
import pytest
from sqlalchemy import select

from httpx import AsyncClient

# Ensure the 'src' package inside this service is importable when running tests
_p = pathlib.Path(__file__).resolve()
service_root = _p.parents[3]
repo_root = _p.parents[5] if len(_p.parents) > 5 else None
sys.path.insert(0, str(service_root))
if repo_root:
    sys.path.insert(0, str(repo_root))

import importlib.util
import types
import uuid

# Ensure internal secret and use a unique test DB filename before loading service modules
os.environ["OUTBOX_INTERNAL_SECRET"] = "testsecret"
test_db_name = f"bot_session_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///./{test_db_name}"

# Load service modules directly to avoid import path issues in test runner
service_src_dir = service_root / "src" / "app"

# Ensure package modules exist so relative imports in `main.py` succeed
pkg_src = types.ModuleType("src")
pkg_src.__path__ = [str(service_root / "src")]
sys.modules["src"] = pkg_src
pkg_app = types.ModuleType("src.app")
pkg_app.__path__ = [str(service_src_dir)]
sys.modules["src.app"] = pkg_app

def _load_service_modules():
    # Ensure fresh imports per test run to avoid cross-test sys.modules contamination
    for k in ("src.app.main", "src.app.db", "src.app.models"):
        if k in sys.modules:
            del sys.modules[k]

    spec_main = importlib.util.spec_from_file_location("src.app.main", service_src_dir / "main.py")
    mod_main = importlib.util.module_from_spec(spec_main)
    sys.modules["src.app.main"] = mod_main
    spec_main.loader.exec_module(mod_main)
    app = mod_main.app

    spec_db = importlib.util.spec_from_file_location("src.app.db", service_src_dir / "db.py")
    mod_db = importlib.util.module_from_spec(spec_db)
    sys.modules["src.app.db"] = mod_db
    spec_db.loader.exec_module(mod_db)
    async_engine = mod_db.async_engine
    Base = mod_db.Base
    AsyncSessionLocal = mod_db.AsyncSessionLocal

    spec_models = importlib.util.spec_from_file_location("src.app.models", service_src_dir / "models.py")
    mod_models = importlib.util.module_from_spec(spec_models)
    sys.modules["src.app.models"] = mod_models
    spec_models.loader.exec_module(mod_models)
    models = mod_models

    return app, async_engine, Base, AsyncSessionLocal, models


@pytest.mark.asyncio
async def test_ice_cycle_upgraded_endpoint():
    os.environ["OUTBOX_INTERNAL_SECRET"] = "testsecret"
    # Load fresh service modules for this test
    app, async_engine, Base, AsyncSessionLocal, models = _load_service_modules()

    # Ensure tables exist
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create a bot + session
    async with AsyncSessionLocal() as db:
        bot = models.Bot(phone_number="000000", type=models.BotType.default, business_id="b1")
        db.add(bot)
        await db.commit()
        await db.refresh(bot)

        s = models.Session(
            user_phone="u1",
            bot_id=bot.id,
            bot_type=bot.type,
            platform="test",
            session_mode=models.SessionMode.public,
            status=models.SessionStatus.active,
            state=models.SessionState.chat,
        )
        db.add(s)
        await db.commit()
        await db.refresh(s)
        session_id = s.id

    headers = {"X-Internal-Secret": "testsecret"}
    payload = {"session_id": session_id, "new_stage": "cart", "snapshot": {"user_text": "hello"}, "event_id": "evt-123"}

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/events/ice.cycle.upgraded", json=payload, headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == session_id
        assert data["new_state"] == "cart"
        cycle_id = data["cycle_id"]

    # Verify session context and cycle metadata
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Session).where(models.Session.id == session_id))
        s2 = res.scalar_one_or_none()
        assert s2 is not None
        assert (s2.object_context or {}).get("cart", {}).get("user_text") == "hello"

        res_c = await db.execute(select(models.SessionStateCycle).where(models.SessionStateCycle.id == cycle_id))
        c = res_c.scalar_one_or_none()
        assert c is not None
        assert (c.meta or {}).get("origin_event_id") == "evt-123"
