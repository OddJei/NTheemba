import asyncio
import os
import json
from datetime import datetime

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.db import SessionLocal, engine
import json


OUTBOX_SINK = os.getenv("OUTBOX_SINK_URL", "http://127.0.0.1:9000/events")
POLL_INTERVAL = float(os.getenv("OUTBOX_POLL_INTERVAL", "2.0"))


async def dispatch_event(session: AsyncSession, row) -> bool:
    try:
        payload = json.loads(row.payload) if row.payload else {}
    except Exception:
        payload = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(OUTBOX_SINK, json={"type": row.topic, "payload": payload})
            resp.raise_for_status()
        except Exception:
            return False

    await session.execute(text("UPDATE public.outbox SET status='sent' WHERE id = :id"), {"id": row.id})
    await session.commit()
    return True


async def run() -> None:
    async with SessionLocal() as session:
        while True:
            res = await session.execute(text("SELECT id, topic, payload::text as payload FROM public.outbox WHERE status = 'pending' ORDER BY created_at ASC LIMIT 50"))
            rows = res.fetchall()
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
