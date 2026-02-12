#!/usr/bin/env python3
import asyncio
import httpx
from sqlalchemy import select
from src.app.db import SessionLocal
from src.app.models import OutboxEvent
from src.app.config import get_affiliate_engine_base_url

async def main():
    async with SessionLocal() as db:
        event = (
            await db.execute(
                select(OutboxEvent)
                .where(OutboxEvent.processed.is_(False))
                .where(OutboxEvent.event_type.in_(["order_created", "order_delivered"]))
                .order_by(OutboxEvent.created_at.desc())
                .limit(1)
            )
        ).scalars().first()

        if not event:
            print("no pending events")
            return

        payload = event.payload or {}
        base = get_affiliate_engine_base_url().rstrip("/")
        url = f"{base}/events/order-created"
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(url, json=payload)
            print("status", r.status_code)
            print("body", r.text[:500])

if __name__ == "__main__":
    asyncio.run(main())
