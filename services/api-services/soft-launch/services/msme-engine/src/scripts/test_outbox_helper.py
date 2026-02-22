import sys
import os
sys.path.insert(0, "/app")
import asyncio
import json
from sqlalchemy import text

from src.app.db import get_db_session


async def main():
    async for db in get_db_session():
        from src.libs.outbox.outbox import create_outbox_row

        payload = {"test": "helper", "timestamp": __import__("datetime").datetime.utcnow().isoformat()}
        try:
            # Ensure any prior failed transaction is cleared
            try:
                await db.rollback()
            except Exception:
                pass

            out_id = await create_outbox_row(db, "msme.test.helper", payload, destination="http://example.local/test", idempotency_key="test-outbox-helper")
            await db.commit()
            out_msg = f"OUTBOX_INSERTED {out_id}\n"
            print(out_msg)
            with open('/tmp/test_outbox_helper.log', 'a') as fh:
                fh.write(out_msg)
        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            err = f"OUTBOX_INSERT_FAILED {str(e)}\n"
            print(err)
            with open('/tmp/test_outbox_helper.log', 'a') as fh:
                fh.write(err)

        # Verify the row exists in public.outbox
        try:
            res = await db.execute(text("SELECT id, topic, destination, payload::text, created_at FROM public.outbox WHERE dedupe_key = :dk ORDER BY created_at DESC LIMIT 5"), {"dk": "test-outbox-helper"})
            rows = res.fetchall()
            v = f"VERIFY_ROWS: {rows}\n"
            print(v)
            with open('/tmp/test_outbox_helper.log', 'a') as fh:
                fh.write(v)
        except Exception as e:
            err = f"VERIFY_FAILED {str(e)}\n"
            print(err)
            with open('/tmp/test_outbox_helper.log', 'a') as fh:
                fh.write(err)


if __name__ == "__main__":
    asyncio.run(main())
