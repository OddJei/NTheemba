import os
import sys
import tempfile
import uuid
from pathlib import Path
from datetime import datetime, timezone

import pytest

# Ensure we can import `src.app.*`
SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

_db_file = Path(tempfile.gettempdir()) / f"order_delivery_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_file.as_posix()}"

# Disable local outbox dispatcher during tests to avoid background DB locks
os.environ["OUTBOX_DISPATCH_ENABLED"] = "false"

from src.app.db import SessionLocal
from src.app import main as od_main
from src.app.models import Order, OutboxEvent
from src.app.helpers.payment_helpers import emit_refund_request, emit_deposit_request, emit_payout_request


@pytest.mark.asyncio
async def test_emit_refund_creates_outbox():
    await od_main.startup()
    try:
        async with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            order = Order(
                session_id=None,
                user_phone="+260971000010",
                user_id=None,
                business_id="biz-help-1",
                status="paid",
                delivery_method="pickup",
                total_amount=1200,
                currency="ZMW",
                meta={},
                created_at=now,
                updated_at=now,
            )
            db.add(order)
            await db.commit()
            await db.refresh(order)

            await emit_refund_request(db, order_id=order.id, amount_minor=1200, currency="ZMW", payment_method={"phone":"260771234567"}, reason="test")

            q = await db.execute(select := __import__("sqlalchemy").select(OutboxEvent).where(OutboxEvent.event_type == "refund_requested"))
            rows = q.scalars().all()
            assert len(rows) >= 1
            payload = rows[-1].payload
            assert payload.get("order_id") == order.id
    finally:
        await od_main.shutdown()


@pytest.mark.asyncio
async def test_emit_deposit_creates_outbox():
    await od_main.startup()
    try:
        async with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            order = Order(
                session_id=None,
                user_phone="+260971000011",
                user_id=None,
                business_id="biz-help-2",
                status="pending_payment",
                delivery_method="pickup",
                total_amount=800,
                currency="ZMW",
                meta={},
                created_at=now,
                updated_at=now,
            )
            db.add(order)
            await db.commit()
            await db.refresh(order)

            await emit_deposit_request(db, order_id=order.id, amount_minor=800, currency="ZMW", phone="260771234000")

            q = await db.execute(__import__("sqlalchemy").select(OutboxEvent).where(OutboxEvent.event_type == "deposit_requested"))
            rows = q.scalars().all()
            assert len(rows) >= 1
            payload = rows[-1].payload
            assert payload.get("order_id") == order.id
    finally:
        await od_main.shutdown()


@pytest.mark.asyncio
async def test_emit_payout_creates_outbox():
    await od_main.startup()
    try:
        async with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            order = Order(
                session_id=None,
                user_phone="+260971000012",
                user_id=None,
                business_id="biz-help-3",
                status="paid",
                delivery_method="pickup",
                total_amount=2000,
                currency="ZMW",
                meta={},
                created_at=now,
                updated_at=now,
            )
            db.add(order)
            await db.commit()
            await db.refresh(order)

            beneficiary = {"account_number": "123", "bank": "test"}
            await emit_payout_request(db, order_id=order.id, amount_minor=1800, currency="ZMW", beneficiary=beneficiary)

            q = await db.execute(__import__("sqlalchemy").select(OutboxEvent).where(OutboxEvent.event_type == "payout_requested"))
            rows = q.scalars().all()
            assert len(rows) >= 1
            payload = rows[-1].payload
            assert payload.get("order_id") == order.id
    finally:
        await od_main.shutdown()
