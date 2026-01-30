import os
import sys
import asyncio
import pytest
from pathlib import Path

# Ensure tests use an in-memory sqlite DB and don't accidentally talk to
# the developer/Postgres DB. Set env before importing app modules.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SERVICE_PORT", "8001")
# Ensure tests default to enabled audit and notifier unless a test overrides them
os.environ["AUDIT_ENABLED"] = "1"
os.environ["NOTIFIER_ENABLED"] = "1"

# Make the notification-service package importable when pytest runs in the
# tests directory by adding the package root to sys.path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
import importlib
import sys
from app.models.db import engine, Base
from app.models import notifications, templates, user_preferences  # ensure models imported

# Ensure settings reflect the test defaults (force True) in case the
# external shell environment has overrides (e.g. when running locally).
settings.AUDIT_ENABLED = True
settings.NOTIFIER_ENABLED = True

# If the FastAPI app module was already imported earlier in this process,
# reload it so it picks up the test-time settings values.
if 'app.main' in sys.modules:
    importlib.reload(sys.modules['app.main'])


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def prepare_db():
    # Some models declare a Postgres schema; for sqlite tests remove it so
    # metadata.create_all works against sqlite.
    for mdl in (notifications.Notification, templates.Template, user_preferences.UserPreference):
        if hasattr(mdl, "__table_args__"):
            try:
                mdl.__table_args__ = {}
            except Exception:
                pass
        # also clear any Table.schema set on the class Table object
        try:
            if hasattr(mdl, "__table__") and getattr(mdl.__table__, "schema", None):
                mdl.__table__.schema = None
        except Exception:
            pass

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

    # Drop tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
