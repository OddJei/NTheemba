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

_db_file = Path(tempfile.gettempdir()) / f"order_notify_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_file.as_posix()}"

from src.app import main as od_main
from src.app.db import SessionLocal
from src.app.models import OutboxEvent
from src.app.helpers.notification_helpers import emit_notification_outbox


@pytest.mark.asyncio
async def test_emit_notification_outbox_order_delivery():
    await od_main.startup()
    try:
        async with SessionLocal() as db:
            oid = await emit_notification_outbox(
                db,
                channel="whatsapp",
                user_id="user-3",
                business_id="biz-3",
                payload={"text": "order update"},
            )

            q = await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "notification.whatsapp"))
            rows = q.scalars().all()
            assert len(rows) >= 1
            assert any(r.id == oid for r in rows)
    finally:
        await od_main.shutdown()
