"""Optional real-runtime proof for an explicitly approved non-production environment."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ntheemba.infrastructure.postgres.migrations import discover_migrations


POSTGRES_DSN = os.getenv("NTHEEMBA_TEST_POSTGRES_DSN", "").strip()
REDIS_URL = os.getenv("NTHEEMBA_TEST_REDIS_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not POSTGRES_DSN or not REDIS_URL,
    reason="set NTHEEMBA_TEST_POSTGRES_DSN and NTHEEMBA_TEST_REDIS_URL for live runtime proof",
)


@pytest.mark.asyncio
async def test_live_postgres_has_all_ntheemba_migrations_and_survives_reconnect() -> None:
    psycopg = pytest.importorskip("psycopg")
    rows = pytest.importorskip("psycopg.rows")
    expected = {item.version for item in discover_migrations(Path("migrations/postgres"))}

    async with await psycopg.AsyncConnection.connect(
        POSTGRES_DSN, autocommit=True, row_factory=rows.dict_row
    ) as connection:
        versions = await (
            await connection.execute("SELECT version FROM schema_migrations ORDER BY version")
        ).fetchall()
        assert expected <= {str(item["version"]) for item in versions}

    async with await psycopg.AsyncConnection.connect(
        POSTGRES_DSN, autocommit=True, row_factory=rows.dict_row
    ) as connection:
        row = await (await connection.execute("SELECT 1 AS ok")).fetchone()
        assert row and row["ok"] == 1


@pytest.mark.asyncio
async def test_live_redis_preserves_probe_across_client_reconnect() -> None:
    redis_asyncio = pytest.importorskip("redis.asyncio")
    client = redis_asyncio.Redis.from_url(REDIS_URL, decode_responses=True)
    key = "ntheemba:n23:pytest-reconnect-proof"
    try:
        assert await client.ping()
        await client.set(key, "preserved", ex=120)
    finally:
        await client.aclose()

    client = redis_asyncio.Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        assert await client.get(key) == "preserved"
        await client.delete(key)
    finally:
        await client.aclose()
