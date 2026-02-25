from __future__ import annotations

import os
import sys
import asyncio
# Ensure project root is on sys.path so `src` package imports work when running this script directly.
root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root not in sys.path:
    sys.path.insert(0, root)
import uuid
import datetime
import json

from sqlalchemy import text

from src.app.db import SessionLocal, engine, Base
from src.libs.outbox.msme_outbox import create_msme_outbox_row
from src.app.helpers.outbox.outbox import create_outbox_row
from src.app.config import get_pg_schema
from src.app.helpers.notification_helpers import emit_notification_outbox


async def main() -> int:
    dedupe_key_msme = f"msme-test-{uuid.uuid4()}"
    dedupe_key_canonical = f"canonical-test-{uuid.uuid4()}"

    # Ensure DB tables exist (helps when using sqlite in local/test runs).
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        # ignore if DB doesn't support create_all for the target schema
        pass

    async with SessionLocal() as session:
        # Determine target table names depending on DB dialect (sqlite lacks schemas)
        schema = get_pg_schema()
        dialect_name = getattr(engine.dialect, "name", "") or ""
        if dialect_name == "sqlite":
            msme_table = "outbox_events"
        else:
            msme_table = f"{schema}.outbox_events"

        # 1) Test msme-specific helper (writes OutboxEvent model -> msme_engine.outbox_events)
        payload = {"event": "msme_smoke", "ts": datetime.datetime.utcnow().isoformat()}
        try:
            await create_msme_outbox_row(
                session,
                topic="msme.test.smoke",
                payload=payload,
                dedupe_key=dedupe_key_msme,
                correlation_id=str(uuid.uuid4()),
                commit=True,
            )
        except Exception as e:
            # Fallback for SQLite/local runs where the ORM-mapped schema table may not exist.
            print("msme_outbox helper failed, falling back to canonical insert:", e)
            await create_outbox_row(
                session,
                "msme.test.smoke",
                payload,
                id=str(uuid.uuid4()),
                destination=None,
                correlation_id=str(uuid.uuid4()),
                idempotency_key=dedupe_key_msme,
                table=msme_table,
            )

        # Verify msme outbox row exists
        q1 = text(f"SELECT id, topic, dedupe_key, payload FROM {msme_table} WHERE dedupe_key = :dk")
        res1 = await session.execute(q1, {"dk": dedupe_key_msme})
        rows1 = res1.fetchall()
        print("MSME OUTBOX ROWS:", rows1)

        # 2) Test canonical helper writing into service schema outbox_events
        schema = get_pg_schema()
        if dialect_name == "sqlite":
            table = "outbox_events"
        else:
            table = f"{schema}.outbox_events"
        canonical_payload = {"event": "canonical_smoke", "ts": datetime.datetime.utcnow().isoformat()}
        await create_outbox_row(
            session,
            "pawapay.deposit.callback",
            canonical_payload,
            id=str(uuid.uuid4()),
            destination="http://example.local/callback",
            correlation_id=str(uuid.uuid4()),
            idempotency_key=dedupe_key_canonical,
            table=table,
        )

        # The helper does not commit by design; commit now.
        try:
            await session.commit()
        except Exception:
            await session.rollback()

        q2 = text(f"SELECT id, topic, dedupe_key, payload FROM {table} WHERE dedupe_key = :dk")
        res2 = await session.execute(q2, {"dk": dedupe_key_canonical})
        rows2 = res2.fetchall()
        print("CANONICAL OUTBOX ROWS:", rows2)

        # 3) Test notification helper (should write to service schema outbox_events as notification.<channel>)
        note_payload = {"msg": "notification smoke", "ts": datetime.datetime.utcnow().isoformat()}
        out_id = await emit_notification_outbox(session, channel="email", user_id=None, business_id=None, payload=note_payload)
        print("NOTIFICATION OUTBOX ID:", out_id)

        # Verify notification row
        q3 = text(f"SELECT id, topic, payload FROM {table} WHERE id = :id")
        res3 = await session.execute(q3, {"id": out_id})
        rows3 = res3.fetchall()
        print("NOTIFICATION OUTBOX ROW:", rows3)

    return 0


if __name__ == "__main__":
    # Ensure project root is on sys.path so `src` imports work when running script directly.
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root not in sys.path:
        sys.path.insert(0, root)

    raise SystemExit(asyncio.run(main()))
