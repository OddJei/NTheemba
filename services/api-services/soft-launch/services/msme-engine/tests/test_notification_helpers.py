import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

# Ensure service package importable
SERVICE_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SERVICE_DIR))

_db_file = Path(tempfile.gettempdir()) / f"msme_notify_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_file.as_posix()}"

from src.app import main as msme_main
from src.app.db import SessionLocal
from src.app.models import OutboxEvent
from src.app.helpers.notification_helpers import emit_notification_outbox


@pytest.mark.asyncio
async def test_emit_notification_outbox_msme():
    await msme_main.startup()
    try:
        async with SessionLocal() as db:
            oid = await emit_notification_outbox(
                db,
                channel="email",
                user_id="user-2",
                business_id="biz-2",
                payload={"subject": "hi"},
            )

            q = await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "notification.email"))
            rows = q.scalars().all()
            assert len(rows) >= 1
            assert any(r.id == oid for r in rows)
    finally:
        await msme_main.shutdown()
