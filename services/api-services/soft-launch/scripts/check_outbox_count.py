#!/usr/bin/env python3
import asyncio
from sqlalchemy import select, func
from src.app.db import SessionLocal
from src.app.models import OutboxEvent

async def main():
    async with SessionLocal() as db:
        result = await db.execute(select(func.count()).select_from(OutboxEvent))
        print("count", result.scalar())
        rows = (await db.execute(select(OutboxEvent).order_by(OutboxEvent.created_at.desc()).limit(3))).scalars().all()
        for r in rows:
            print(r.event_type, r.processed, (r.payload or {}).get("affiliate_id"))

if __name__ == "__main__":
    asyncio.run(main())
