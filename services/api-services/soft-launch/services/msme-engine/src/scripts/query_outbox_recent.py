import os
import asyncio
import json

import asyncpg


async def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL not set in environment")
        return
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT id::text as id, topic, payload, created_at FROM msme_engine.outbox_events ORDER BY created_at DESC LIMIT 10"
        )
        out = []
        for r in rows:
            out.append({"id": r["id"], "topic": r["topic"], "payload": r["payload"], "created_at": str(r["created_at"])})
        print(json.dumps(out, indent=2, default=str))
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
