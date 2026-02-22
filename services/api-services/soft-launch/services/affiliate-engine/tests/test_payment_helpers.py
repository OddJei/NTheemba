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

_db_file = Path(tempfile.gettempdir()) / f"affiliate_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_file.as_posix()}"

from src.app import main as aff_main
from src.app.db import SessionLocal
from src.app.models import Outbox
from src.app.helpers.payment_helpers import emit_affiliate_payout_request


@pytest.mark.asyncio
async def test_emit_affiliate_payout_creates_outbox():
    # Start service to create tables
    await aff_main.startup()
    try:
        async with SessionLocal() as db:
            eid = await emit_affiliate_payout_request(
                db,
                affiliate_id="aff-1",
                order_id="ord-1",
                business_id="biz-1",
                amount_zmw=123.45,
                currency="ZMW",
                correlation_id="corr-1",
            )

            q = await db.execute(select(Outbox).where(Outbox.topic == "payout_requested"))
            rows = q.scalars().all()
            assert len(rows) >= 1
            found = any(r.dedupe_key == eid for r in rows)
            assert found
    finally:
        await aff_main.shutdown()
