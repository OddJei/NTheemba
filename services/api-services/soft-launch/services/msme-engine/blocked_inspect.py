import asyncio
import os
import json

import asyncpg

async def main():
    # Read connection info from env or fallback to .env values
    user = os.environ.get("PG_USER", os.environ.get("PGUSER", "postgres"))
    password = os.environ.get("PG_PASSWORD", os.environ.get("PGPASSWORD", "!ladybug!#!"))
    host = os.environ.get("PG_HOST", os.environ.get("PGHOST", "127.0.0.1"))
    port = int(os.environ.get("PG_PORT", os.environ.get("PGPORT", 5432)))
    database = os.environ.get("PG_DB", os.environ.get("PGDATABASE", "ntheemba"))

    print(f"Connecting to {host}:{port}/{database} as {user}")
    conn = None
    try:
        conn = await asyncpg.connect(user=user, password=password, host=host, port=port, database=database)
        sql = """
WITH blocked AS (
  SELECT pid AS blocked_pid, pg_blocking_pids(pid) AS blockers, query AS blocked_query
  FROM pg_stat_activity
  WHERE pid <> pg_backend_pid() AND state <> 'idle'
)
SELECT b.blocked_pid, b.blocked_query, bp.blocking_pid, a.query AS blocking_query
FROM blocked b
CROSS JOIN LATERAL unnest(b.blockers) AS bp(blocking_pid)
JOIN pg_stat_activity a ON a.pid = bp.blocking_pid;
"""
        rows = await conn.fetch(sql)
        if not rows:
            print("No blocked/blocking relationships found.")
            return
        for r in rows:
            # print as JSON for easy parsing
            print(json.dumps({
                "blocked_pid": r["blocked_pid"],
                "blocked_query": r["blocked_query"],
                "blocking_pid": r["blocking_pid"],
                "blocking_query": r["blocking_query"],
            }, default=str))
    except Exception as exc:
        import traceback
        traceback.print_exc()
        if conn is not None:
            try:
                await conn.close()
            except Exception:
                pass
        raise
    finally:
        if conn is not None:
            try:
                await conn.close()
            except Exception:
                pass

if __name__ == "__main__":
    asyncio.run(main())
