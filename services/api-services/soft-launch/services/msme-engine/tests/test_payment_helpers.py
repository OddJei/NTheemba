import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

# Ensure service package importable
SERVICE_DIR = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SERVICE_DIR))

_db_file = Path(tempfile.gettempdir()) / f"msme_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_file.as_posix()}"

from src.app import main as msme_main
from src.app.db import SessionLocal
from src.app.models import OutboxEvent
from src.app.helpers.payment_helpers import emit_subscription_deposit_request


@pytest.mark.asyncio
async def test_emit_subscription_deposit_creates_outboxevent():
    await msme_main.startup()
    try:
        async with SessionLocal() as db:
            eid = await emit_subscription_deposit_request(
                db,
                business_id="biz-1",
                subscription_id="sub-1",
                amount_minor=5000,
                currency="ZMW",
                phone="260971000000",
                correlation_id="corr-sub-1",
            )

            q = await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "deposit_requested"))
            rows = q.scalars().all()
            assert len(rows) >= 1
            # At least one outbox event payload should contain subscription_id
            assert any((r.payload or {}).get("subscription_id") == "sub-1" for r in rows)
    finally:
        await msme_main.shutdown()
