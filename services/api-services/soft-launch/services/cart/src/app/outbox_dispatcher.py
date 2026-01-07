from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
from sqlalchemy import select

from src.app.db import SessionLocal
from src.app.models import OutboxEvent


def _sink_url() -> str:
    url = os.getenv("EVENT_SINK_URL", "").strip()
    if not url:
        raise RuntimeError("EVENT_SINK_URL is required to dispatch outbox events")
    return url


async def dispatch_once(*, batch_size: int = 50) -> int:
    sink_url = _sink_url()

    async with SessionLocal() as db:
        events = (
            await db.execute(
                select(OutboxEvent)
                .where(OutboxEvent.processed.is_(False))
                .order_by(OutboxEvent.created_at.asc())
                .limit(int(batch_size))
            )
        ).scalars().all()

        if not events:
            return 0

        async with httpx.AsyncClient(timeout=10.0) as client:
            for ev in events:
                body: dict[str, Any] = {
                    "id": ev.id,
                    "event_type": ev.event_type,
                    "business_id": ev.business_id,
                    "entity_type": ev.entity_type,
                    "entity_id": ev.entity_id,
                    "payload": ev.payload,
                    "correlation_id": ev.correlation_id,
                    "created_at": ev.created_at.isoformat(),
                }

                # basic retry
                last_exc: Exception | None = None
                for attempt in range(3):
                    try:
                        resp = await client.post(sink_url, json=body)
                        if 200 <= resp.status_code < 300:
                            last_exc = None
                            break
                        last_exc = RuntimeError(f"sink_status_{resp.status_code}")
                    except Exception as exc:  # noqa: BLE001
                        last_exc = exc
                    await asyncio.sleep(0.25 * (2**attempt))

                if last_exc is not None:
                    # stop processing batch; will retry next run
                    break

                ev.processed = True
                await db.commit()

        return len([e for e in events if e.processed])


async def run_forever(*, poll_seconds: float = 2.0, batch_size: int = 50) -> None:
    while True:
        processed = await dispatch_once(batch_size=batch_size)
        if processed == 0:
            await asyncio.sleep(float(poll_seconds))


if __name__ == "__main__":
    asyncio.run(run_forever())
