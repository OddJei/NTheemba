from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
import json
from sqlalchemy import select, text
from src.app.config import (
    get_affiliate_engine_base_url,
    get_affiliate_engine_timeout_seconds,
    get_payment_revenue_base_url,
    get_payment_revenue_timeout_seconds,
)
from src.app.db import SessionLocal
from src.app.helpers.outbox.outbox import create_outbox_row

logger = logging.getLogger("order-delivery")


async def dispatch_once(*, batch_size: int = 50) -> int:
    # Determine destination base and timeout depending on event type.
    timeout = get_affiliate_engine_timeout_seconds()

    async with SessionLocal() as db:
        sql = text(
            """
            SELECT id, topic, payload::text as payload, destination, dedupe_key, attempts, correlation_id
            FROM public.outbox
            WHERE status = 'pending' AND topic = ANY(:topics)
            ORDER BY created_at ASC
            LIMIT :limit
            """
        )
        topics = ["order_created", "order_delivered", "deposit_requested", "payout_requested"]
        res = await db.execute(sql, {"topics": topics, "limit": int(batch_size)})
        rows = res.fetchall()

        if not rows:
            return 0

        dispatched = 0
        async with httpx.AsyncClient(timeout=timeout) as client:
            for r in rows:
                try:
                    payload = json.loads(r.payload) if r.payload else {}
                except Exception:
                    payload = {}

                topic = r.topic

                # Derive destination and timeout if not explicit
                if r.destination:
                    destination = r.destination
                    base = ""
                    timeout = get_payment_revenue_timeout_seconds()
                else:
                    if topic in ("order_created", "order_delivered"):
                        base = get_affiliate_engine_base_url().rstrip("/")
                        destination = "/events/order-created" if topic == "order_created" else "/events/order/delivered"
                        timeout = get_affiliate_engine_timeout_seconds()
                    elif topic == "deposit_requested":
                        base = get_payment_revenue_base_url().rstrip("/")
                        destination = "/pawapay/deposits/initiate"
                        timeout = get_payment_revenue_timeout_seconds()
                    elif topic == "payout_requested":
                        base = get_payment_revenue_base_url().rstrip("/")
                        destination = "/msme/payouts/initiate"
                        timeout = get_payment_revenue_timeout_seconds()
                    else:
                        # Unknown topic -> mark sent to avoid stuck rows
                        await db.execute(text("UPDATE public.outbox SET status='sent' WHERE id = :id"), {"id": r.id})
                        await db.commit()
                        continue

                # Basic validation for affiliate events
                if topic in ("order_created", "order_delivered"):
                    affiliate_code = payload.get("affiliate_code")
                    affiliate_id = payload.get("affiliate_id")
                    if not (affiliate_code or affiliate_id):
                        await db.execute(text("UPDATE public.outbox SET status='sent' WHERE id = :id"), {"id": r.id})
                        await db.commit()
                        continue

                correlation_id = payload.get("correlation_id") or ""
                headers: dict[str, str] = {}
                if isinstance(correlation_id, str) and correlation_id:
                    headers["X-Correlation-Id"] = correlation_id

                event_id = payload.get("event_id") or payload.get("order_id")
                if isinstance(event_id, str) and event_id:
                    headers["X-Idempotency-Key"] = event_id

                last_exc: Exception | None = None
                for attempt in range(3):
                    try:
                        url = f"{base}{destination}" if base else destination
                        resp = await client.post(url, json=payload, headers=headers, timeout=timeout)
                        if 200 <= resp.status_code < 300:
                            last_exc = None
                            break
                        last_exc = RuntimeError(f"status_{resp.status_code}")
                    except Exception as exc:  # noqa: BLE001
                        last_exc = exc
                    await asyncio.sleep(0.25 * (2**attempt))

                if last_exc is not None:
                    break

                await db.execute(text("UPDATE public.outbox SET status='sent' WHERE id = :id"), {"id": r.id})
                await db.commit()
                dispatched += 1

        return dispatched


async def run_forever(*, poll_seconds: float = 2.0, batch_size: int = 50) -> None:
    logger.info("OUTBOX_DISPATCHER_STARTED", extra={"poll_seconds": poll_seconds, "batch_size": batch_size})
    while True:
        try:
            processed = await dispatch_once(batch_size=batch_size)
            if processed > 0:
                logger.info("OUTBOX_DISPATCHER_PROCESSED", extra={"count": processed})
            else:
                await asyncio.sleep(float(poll_seconds))
        except Exception as e:
            logger.error("OUTBOX_DISPATCHER_ERROR", extra={"error": str(e)})
            await asyncio.sleep(float(poll_seconds))


if __name__ == "__main__":
    asyncio.run(run_forever())