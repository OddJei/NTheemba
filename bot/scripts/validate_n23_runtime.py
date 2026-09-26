"""Validate real Ntheemba PostgreSQL/Redis runtime readiness and restart persistence."""

from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ntheemba.infrastructure.postgres.migrations import discover_migrations


async def _postgres(dsn: str, migrations_dir: Path) -> dict[str, object]:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as error:
        return {"status": "BLOCKED", "detail": f"psycopg unavailable: {error}"}
    expected = {item.version for item in discover_migrations(migrations_dir)}
    async with await psycopg.AsyncConnection.connect(
        dsn, autocommit=True, row_factory=dict_row
    ) as connection:
        row = await (await connection.execute("SELECT 1 AS ok")).fetchone()
        versions = await (
            await connection.execute("SELECT version FROM schema_migrations ORDER BY version")
        ).fetchall()
    applied = {str(item["version"]) for item in versions}
    missing = sorted(expected - applied)
    return {
        "status": "PASS" if row and row["ok"] == 1 and not missing else "FAIL",
        "applied_migrations": len(applied),
        "expected_migrations": len(expected),
        "missing_migrations": missing,
    }


async def _redis(url: str, *, mode: str, token: str | None) -> dict[str, object]:
    try:
        from redis.asyncio import Redis
    except ImportError as error:
        return {"status": "BLOCKED", "detail": f"redis package unavailable: {error}"}
    client = Redis.from_url(url, decode_responses=True, socket_timeout=5)
    try:
        if not await client.ping():
            return {"status": "FAIL", "detail": "Redis ping failed"}
        if mode == "prepare":
            value = token or secrets.token_urlsafe(18)
            key = f"ntheemba:n23:restart-proof:{value}"
            await client.set(key, value, ex=3600)
            return {"status": "PASS", "restart_token": value, "detail": "restart proof prepared"}
        if mode == "verify":
            if not token:
                return {"status": "FAIL", "detail": "restart token required for verify"}
            key = f"ntheemba:n23:restart-proof:{token}"
            value = await client.get(key)
            if value != token:
                return {"status": "FAIL", "detail": "Redis restart proof key was not preserved"}
            await client.delete(key)
            return {"status": "PASS", "detail": "restart proof preserved and removed"}
        probe = secrets.token_urlsafe(12)
        key = f"ntheemba:n23:connection-proof:{probe}"
        await client.set(key, probe, ex=60)
        await client.aclose()
        client = Redis.from_url(url, decode_responses=True, socket_timeout=5)
        value = await client.get(key)
        await client.delete(key)
        return {
            "status": "PASS" if value == probe else "FAIL",
            "detail": "Redis client reconnect preserved state" if value == probe else "Redis reconnect lost state",
        }
    except Exception as error:
        return {"status": "FAIL", "detail": type(error).__name__}
    finally:
        await client.aclose()


async def run(args: argparse.Namespace) -> int:
    results = {
        "postgres": await _postgres(args.postgres_dsn, args.migrations),
        "redis": await _redis(args.redis_url, mode=args.restart_mode, token=args.restart_token),
    }
    print(json.dumps(results, indent=2, sort_keys=True))
    statuses = {str(item.get("status")) for item in results.values()}
    if "FAIL" in statuses:
        return 1
    if "BLOCKED" in statuses:
        return 2
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-dsn", required=True)
    parser.add_argument("--redis-url", required=True)
    parser.add_argument("--migrations", type=Path, default=Path("migrations/postgres"))
    parser.add_argument("--restart-mode", choices=("none", "prepare", "verify"), default="none")
    parser.add_argument("--restart-token")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
