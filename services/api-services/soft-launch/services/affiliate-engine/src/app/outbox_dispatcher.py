from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
from sqlalchemy import select

from src.app.db import SessionLocal
from src.app.models import AffiliateEvent
from src.app.models import utcnow


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
                select(AffiliateEvent)
                .where(AffiliateEvent.dispatched_at.is_(None))
                .order_by(AffiliateEvent.created_at.asc())
                .limit(int(batch_size))
            )
        ).scalars().all()

        if not events:
            return 0

        dispatched = 0

        async with httpx.AsyncClient(timeout=10.0) as client:
            for ev in events:
                body: dict[str, Any] = {
                    "event_id": ev.event_id,
                    "event_type": ev.event_type,
                    "affiliate_id": ev.affiliate_id,
                    "order_id": ev.order_id,
                    "business_id": ev.business_id,
                    "amount_zmw": ev.amount_zmw,
                    "correlation_id": ev.correlation_id,
                    "meta": ev.meta,
                    "occurred_at": ev.occurred_at.isoformat(),
                }

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
                    break

                # Mark as dispatched so we don't re-send on next poll.
                ev.dispatched_at = utcnow()
                await db.commit()
                dispatched += 1

            return dispatched


async def run_forever(*, poll_seconds: float = 2.0, batch_size: int = 50) -> None:
    while True:
        processed = await dispatch_once(batch_size=batch_size)
        if processed == 0:
            await asyncio.sleep(float(poll_seconds))


if __name__ == "__main__":
    asyncio.run(run_forever())
