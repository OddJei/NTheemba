import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.app.models import Base, Business, SubscriptionReminder
from src.app.jobs.subscription_reminder import process_due_subscriptions


@pytest.mark.asyncio
async def test_process_due_creates_reminder_and_attempts(monkeypatch):
    # In-memory sqlite engine
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # prevent real HTTP calls
    class DummyClient:
        async def post(self, *a, **k):
            class R:
                status_code = 200

            return R()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("src.app.jobs.subscription_reminder.httpx.AsyncClient", lambda timeout: DummyClient())

    async with AsyncSessionLocal() as db:
        # create a paid business that is already expired so process triggers auto-pay
        biz = Business(name="Tst", owner_id="u1", subscription_plan="paid", subscription_expiry=datetime.now(timezone.utc) - timedelta(seconds=1), is_active=True)
        db.add(biz)
        await db.commit()

        # capture audit emits
        calls = []

        def fake_emit(*a, **k):
            calls.append({"args": a, "kwargs": k})

        monkeypatch.setattr("src.app.jobs.subscription_reminder.emit_audit_sync", fake_emit)

        await process_due_subscriptions(db)

        rem = (await db.execute(SubscriptionReminder.__table__.select())).first()
        assert rem is not None
        # ensure auto_pay_attempted was set
        r = (await db.execute(SubscriptionReminder.__table__.select())).mappings().first()
        assert r is not None
        assert r["auto_pay_attempted"] in (1, True)

        # ensure audit emit for auto-pay attempt was called
        assert any(call["args"][1] == "subscription_auto_pay_attempt" for call in calls)
