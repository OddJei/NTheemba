import sys
sys.path.insert(0, "/app")

import asyncio
from sqlalchemy import text

from src.app.db import engine


async def main():
    from src.libs.outbox.outbox import create_outbox_row

    dedupe = "test-outbox-helper-conn"
    payload = {"test": "helper-conn"}

    async with engine.begin() as conn:
        try:
            out_id = await create_outbox_row(conn, "msme.test.helper.conn", payload, destination="http://example.local/test", idempotency_key=dedupe)
            # commit is handled by the connection context manager
            print("OUTBOX_INSERTED", out_id)
        except Exception as e:
            print("OUTBOX_INSERT_FAILED", repr(e))

        # Verify using the same connection
        try:
            res = await conn.execute(text("SELECT id, topic, destination, payload::text, created_at FROM public.outbox WHERE dedupe_key = :dk ORDER BY created_at DESC LIMIT 5"), {"dk": dedupe})
            rows = res.fetchall()
            print("VERIFY_ROWS:", rows)
        except Exception as e:
            print("VERIFY_FAILED", repr(e))


if __name__ == "__main__":
    asyncio.run(main())
