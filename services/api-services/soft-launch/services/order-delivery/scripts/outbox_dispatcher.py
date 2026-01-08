import asyncio
import os
import json
from datetime import datetime

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.db import SessionLocal, engine
from src.app.models import OutboxEvent


OUTBOX_SINK = os.getenv("OUTBOX_SINK_URL", "http://127.0.0.1:9000/events")
POLL_INTERVAL = float(os.getenv("OUTBOX_POLL_INTERVAL", "2.0"))


async def dispatch_event(session: AsyncSession, event: OutboxEvent) -> bool:
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(OUTBOX_SINK, json={"type": event.event_type, "payload": event.payload})
            resp.raise_for_status()
        except Exception:
            return False

    # mark processed
    await session.execute(
        update(OutboxEvent).where(OutboxEvent.id == event.id).values(processed=True)
    )
    await session.commit()
    return True


async def run() -> None:
    async with SessionLocal() as session:
        while True:
            rows = (await session.execute(select(OutboxEvent).where(OutboxEvent.processed == False))).scalars().all()
            if not rows:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            for ev in rows:
                ok = await dispatch_event(session, ev)
                if not ok:
                    # backoff and retry later
                    await asyncio.sleep(1.0)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("outbox dispatcher stopped")
