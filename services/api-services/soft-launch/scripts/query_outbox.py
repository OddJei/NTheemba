#!/usr/bin/env python3
"""Query payment-revenue database to inspect PawaPayDeposit and Outbox records."""
import sys
import asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://postgres:!ladybug!%23!@localhost:5432/ntheemba"
SCHEMA = "payment_revenue"


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Query PawaPayDeposit records
        print("=" * 70)
        print("PAWAPAY DEPOSITS (last 5)")
        print("=" * 70)
        result = await db.execute(
            text(f"""
                SELECT deposit_id, status, business_id, amount_minor, meta 
                FROM {SCHEMA}.pawapay_deposits 
                ORDER BY created_at DESC 
                LIMIT 5
            """)
        )
        rows = result.fetchall()
        print(f"Rows: {len(rows)}")
        for row in rows:
            deposit_id, status, business_id, amount_minor, meta = row
            print(f"Deposit ID: {deposit_id}")
            print(f"  Status: {status}")
            print(f"  Business ID: {business_id}")
            print(f"  Amount: {amount_minor}")
            print(f"  Meta: {meta}")
            if meta:
                initiator = meta.get("initiator_id", "UNKNOWN")
                print(f"  Initiator ID: {initiator}")
            print()

        # Query Outbox records (all statuses for audit trail)
        print("=" * 70)
        print("OUTBOX EVENTS (last 10, all statuses)")
        print("=" * 70)
        result = await db.execute(
            text(f"""
                SELECT id, topic, destination, payload, status, attempts, last_error, send_after, created_at
                FROM {SCHEMA}.outbox 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
        )
        rows = result.fetchall()
        if not rows:
            print("[NO OUTBOX ENTRIES]")
        else:
            # Show summary
            result2 = await db.execute(
                text(f"""
                    SELECT status, count(*) FROM {SCHEMA}.outbox GROUP BY status
                """)
            )
            print("Summary by status:")
            for status, count in result2:
                print(f"  {status}: {count}")
            print()
            
        for row in rows:
            id_, topic, destination, payload, status, attempts, last_error, send_after, created_at = row
            print(f"Outbox ID: {id_}")
            print(f"  Topic: {topic}")
            print(f"  Destination: {destination}")
            print(f"  Status: {status}")
            print(f"  Attempts: {attempts}")
            print(f"  Created: {created_at}")
            if last_error:
                print(f"  Last Error: {last_error}")
            if send_after:
                print(f"  Send After: {send_after}")
            event_type = payload.get("event_type") if isinstance(payload, dict) else None
            if event_type:
                print(f"  Event Type: {event_type}")
            print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
