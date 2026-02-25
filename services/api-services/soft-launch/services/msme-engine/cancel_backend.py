import os
import sys
import asyncio

import asyncpg

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 8868

# Prefer DATABASE_URL if present; otherwise connect to localhost database
dsn = os.environ.get("DATABASE_URL") or os.environ.get("PG_CONN") or "postgresql://postgres@127.0.0.1:5432/ntheemba"

async def main():
    print("Using DSN:", dsn)
    try:
        conn = await asyncpg.connect(dsn)
    except Exception as e:
        print("CONNECT_ERROR:", e)
        raise
    try:
        res = await conn.fetchval("SELECT pg_cancel_backend($1);", PID)
        print("pg_cancel_backend returned:", res)
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
