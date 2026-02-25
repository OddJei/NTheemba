import os
import asyncio
import asyncpg
import json

dsn = os.getenv('DATABASE_URL')
if not dsn:
    raise SystemExit('DATABASE_URL not set')
if dsn.startswith('postgresql+asyncpg://'):
    dsn = dsn.replace('postgresql+asyncpg://', 'postgresql://')

async def main():
    conn = await asyncpg.connect(dsn)
    cols = await conn.fetch("""
        select column_name
        from information_schema.columns
        where table_schema='msme_engine' and table_name='outbox_events'
        order by ordinal_position
    """)
    col_list = [r['column_name'] for r in cols]
    print('columns:', col_list)
    rows = await conn.fetch('select * from msme_engine.outbox_events order by created_at desc limit 10')
    out = []
    for r in rows:
        out.append({k: r[k] for k in col_list if k in r})
    print(json.dumps(out, default=str, indent=2))
    await conn.close()

asyncio.run(main())
