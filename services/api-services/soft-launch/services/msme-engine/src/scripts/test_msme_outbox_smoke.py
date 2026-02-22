from __future__ import annotations

import sys
sys.path.insert(0, "/app")

import asyncio
import json
import uuid
import datetime

from sqlalchemy import text

from src.app.db import SessionLocal
from libs.outbox.msme_outbox import create_msme_outbox_row


async def main() -> int:
    dedupe_key = f"smoke-test-{uuid.uuid4()}"
        payload = {"event": "smoke", "created_at": datetime.datetime.utcnow().isoformat()}

    async with SessionLocal() as session:
        # Insert and commit (helper commits by default)
        await create_msme_outbox_row(
            session,
            topic="msme.subscription.test_smoke",
            payload=payload,
            dedupe_key=dedupe_key,
            correlation_id=str(uuid.uuid4()),
            commit=True,
        )

        # Verify the row exists
        q = text(
            "SELECT id, topic, dedupe_key, created_at FROM msme_engine.outbox_events WHERE dedupe_key = :dk"
        )
        result = await session.execute(q, {"dk": dedupe_key})
        rows = result.fetchall()

        print("VERIFY_ROWS:", rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
