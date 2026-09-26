"""Prove local N23 PostgreSQL/Redis reconnect behavior without external services."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

from ntheemba.infrastructure.postgres.migrations import discover_migrations


async def prove() -> dict[str, object]:
    """Validate the local durable stores used by the Ntheemba runtime."""

    postgres_dsn = os.getenv("NTHEEMBA_TEST_POSTGRES_DSN", "").strip()
    redis_url = os.getenv("NTHEEMBA_TEST_REDIS_URL", "").strip()
    if not postgres_dsn or not redis_url:
        raise RuntimeError("NTHEEMBA_TEST_POSTGRES_DSN and NTHEEMBA_TEST_REDIS_URL are required")

    import psycopg
    import redis.asyncio as redis_asyncio
    from psycopg.rows import dict_row

    expected_migrations = {
        item.version for item in discover_migrations(Path("migrations/postgres"))
    }
    async with await psycopg.AsyncConnection.connect(
        postgres_dsn,
        autocommit=True,
        row_factory=dict_row,
    ) as connection:
        versions = await (
            await connection.execute("SELECT version FROM schema_migrations ORDER BY version")
        ).fetchall()
    applied_migrations = {str(item["version"]) for item in versions}
    if not expected_migrations <= applied_migrations:
        missing = sorted(expected_migrations - applied_migrations)
        raise RuntimeError(f"local PostgreSQL is missing migrations: {', '.join(missing)}")

    async with await psycopg.AsyncConnection.connect(
        postgres_dsn,
        autocommit=True,
        row_factory=dict_row,
    ) as connection:
        row = await (await connection.execute("SELECT 1 AS ok")).fetchone()
        await _assert_business_capability_catalogue(connection)
    if row is None or row["ok"] != 1:
        raise RuntimeError("local PostgreSQL reconnect probe failed")

    key = f"ntheemba:n23:runtime-proof:{uuid4().hex}"
    first_client = redis_asyncio.Redis.from_url(redis_url, decode_responses=True)
    try:
        if not await first_client.ping():
            raise RuntimeError("local Redis ping failed")
        await first_client.set(key, "preserved", ex=120)
    finally:
        await first_client.aclose()

    second_client = redis_asyncio.Redis.from_url(redis_url, decode_responses=True)
    try:
        if await second_client.get(key) != "preserved":
            raise RuntimeError("local Redis reconnect probe failed")
    finally:
        await second_client.delete(key)
        await second_client.aclose()

    return {
        "status": "passed",
        "postgres_migrations": len(applied_migrations),
        "business_capability_catalogue_enforced": True,
        "redis_reconnect": True,
    }


async def _assert_business_capability_catalogue(connection: object) -> None:
    """Prove direct writes cannot smuggle platform/unknown capability aliases."""

    # `connection` is psycopg's async connection at runtime.  Keeping this
    # narrow proof independent of application parsing is deliberate: PostgreSQL
    # must reject invalid direct persistence on its own.
    probe_business_id = f"n23-capability-proof-{uuid4().hex}"
    try:
        await connection.execute(  # type: ignore[attr-defined]
            """
            INSERT INTO businesses (
                business_id, display_name, adapter_type, business_type, description
            ) VALUES (%s, 'N23 capability proof', 'tradeflow_standard', 'proof', 'local')
            """,
            (probe_business_id,),
        )
        for capability_id in ("platform_marketplace", "business.unreviewed_capability"):
            try:
                async with connection.transaction():  # type: ignore[attr-defined]
                    await connection.execute(  # type: ignore[attr-defined]
                        """
                        INSERT INTO business_capabilities (business_id, capability_id)
                        VALUES (%s, %s)
                        """,
                        (probe_business_id, capability_id),
                    )
            except Exception:
                continue
            raise RuntimeError(
                f"local PostgreSQL accepted invalid business capability {capability_id!r}"
            )
    finally:
        await connection.execute(  # type: ignore[attr-defined]
            "DELETE FROM businesses WHERE business_id = %s",
            (probe_business_id,),
        )


def main() -> None:
    """Run the proof and emit a small non-secret result envelope."""

    print(json.dumps(asyncio.run(prove()), sort_keys=True))


if __name__ == "__main__":
    main()
