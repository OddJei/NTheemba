import os
import asyncio
import asyncpg
import json

dsn = os.getenv('DATABASE_URL')
if not dsn:
    raise SystemExit('DATABASE_URL not set')
# asyncpg expects postgresql:// not postgresql+asyncpg://
if dsn.startswith('postgresql+asyncpg://'):
    dsn = dsn.replace('postgresql+asyncpg://', 'postgresql://')

async def main():
    conn = await asyncpg.connect(dsn)
    rows = await conn.fetch(
        'select id::text, topic, destination, status, created_at, last_error from msme_engine.outbox_events order by created_at desc limit 10'
    )
    out = [dict(r) for r in rows]
    print(json.dumps(out, default=str, indent=2))
    await conn.close()

asyncio.run(main())
