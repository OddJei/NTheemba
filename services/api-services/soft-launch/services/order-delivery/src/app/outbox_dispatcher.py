from __future__ import annotations

import asyncio
from typing import Any

import httpx
from sqlalchemy import select

from src.app.config import get_affiliate_engine_base_url, get_affiliate_engine_timeout_seconds
from src.app.db import SessionLocal
from src.app.models import OutboxEvent


async def dispatch_once(*, batch_size: int = 50) -> int:
    base = get_affiliate_engine_base_url().rstrip("/")
    timeout = get_affiliate_engine_timeout_seconds()

    async with SessionLocal() as db:
        events = (
            await db.execute(
                select(OutboxEvent)
                .where(OutboxEvent.processed.is_(False))
                .where(OutboxEvent.event_type == "order_created")
                .order_by(OutboxEvent.created_at.asc())
                .limit(int(batch_size))
            )
        ).scalars().all()

        if not events:
            return 0

        dispatched = 0
        async with httpx.AsyncClient(timeout=timeout) as client:
            for ev in events:
                payload: dict[str, Any] = ev.payload or {}
                affiliate_code = payload.get("affiliate_code")
                if not affiliate_code:
                    ev.processed = True
                    await db.commit()
                    continue

                correlation_id = payload.get("correlation_id") or ""
                headers: dict[str, str] = {}
                if isinstance(correlation_id, str) and correlation_id:
                    headers["X-Correlation-Id"] = correlation_id

                event_id = payload.get("event_id")
                if isinstance(event_id, str) and event_id:
                    headers["X-Idempotency-Key"] = event_id

                last_exc: Exception | None = None
                for attempt in range(3):
                    try:
                        resp = await client.post(f"{base}/events/order-created", json=payload, headers=headers)
                        if 200 <= resp.status_code < 300:
                            last_exc = None
                            break
                        last_exc = RuntimeError(f"affiliate_engine_status_{resp.status_code}")
                    except Exception as exc:  # noqa: BLE001
                        last_exc = exc
                    await asyncio.sleep(0.25 * (2**attempt))

                if last_exc is not None:
                    break

                ev.processed = True
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