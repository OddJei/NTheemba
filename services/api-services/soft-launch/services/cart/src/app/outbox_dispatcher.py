from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
import json
from sqlalchemy import text

from src.app.db import SessionLocal
from datetime import datetime


def _sink_url() -> str:
    url = os.getenv("EVENT_SINK_URL", "").strip()
    if not url:
        raise RuntimeError("EVENT_SINK_URL is required to dispatch outbox events")
    return url


async def dispatch_once(*, batch_size: int = 50) -> int:
    sink_url = _sink_url()

    async with SessionLocal() as db:
        sql = text(
            """
            SELECT id, topic, payload::text as payload, dedupe_key, destination, attempts, scheduled_at, correlation_id
            FROM public.outbox
            WHERE status = 'pending' AND producer = 'cart'
            ORDER BY created_at ASC
            LIMIT :limit
            """
        )
        res = await db.execute(sql, {"limit": int(batch_size)})
        rows = res.fetchall()
        if not rows:
            return 0

        async with httpx.AsyncClient(timeout=10.0) as client:
            processed = 0
            for r in rows:
                try:
                    payload = json.loads(r.payload) if r.payload else {}
                except Exception:
                    payload = {}
                body: dict[str, Any] = {
                    "id": str(r.id),
                    "event_type": r.topic,
                    "business_id": None,
                    "entity_type": None,
                    "entity_id": None,
                    "payload": payload,
                    "correlation_id": r.correlation_id,
                    "created_at": None,
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

                await db.execute(text("UPDATE public.outbox SET status='sent', updated_at = :now WHERE id = :id"), {"id": r.id, "now": datetime.utcnow()})
                await db.commit()
                processed += 1

        return processed


async def run_forever(*, poll_seconds: float = 2.0, batch_size: int = 50) -> None:
    while True:
        processed = await dispatch_once(batch_size=batch_size)
        if processed == 0:
            await asyncio.sleep(float(poll_seconds))


if __name__ == "__main__":
    asyncio.run(run_forever())
