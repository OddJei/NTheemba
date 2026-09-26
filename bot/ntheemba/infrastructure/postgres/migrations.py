"""Ordered PostgreSQL migration discovery and application helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_VERSION_RE = re.compile(
    r"INSERT\s+INTO\s+schema_migrations\s*\([^)]*version[^)]*\)\s*"
    r"VALUES\s*\(\s*'([^']+)'",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class PostgresMigration:
    """One ordered migration file and its durable schema version identifier."""

    path: Path
    version: str
    sql: str


def discover_migrations(directory: Path) -> tuple[PostgresMigration, ...]:
    """Load migrations in filename order and require one unique durable version each."""

    files = sorted(directory.glob("*.sql"))
    if not files:
        raise RuntimeError(f"No migration files found in {directory}")
    migrations: list[PostgresMigration] = []
    seen: set[str] = set()
    for path in files:
        sql = path.read_text(encoding="utf-8")
        match = _VERSION_RE.search(sql)
        if match is None:
            raise RuntimeError(f"Migration {path.name} does not record schema_migrations.version")
        version = match.group(1)
        if version in seen:
            raise RuntimeError(f"Duplicate PostgreSQL migration version {version!r}")
        seen.add(version)
        migrations.append(PostgresMigration(path=path, version=version, sql=sql))
    return tuple(migrations)


async def applied_versions(connection: Any) -> frozenset[str]:
    """Return durable migration versions, or an empty set for a fresh database."""

    cursor = await connection.execute(
        "SELECT to_regclass('public.schema_migrations') AS schema_migrations"
    )
    row = await cursor.fetchone()
    if row is None:
        return frozenset()
    value = row["schema_migrations"] if isinstance(row, dict) else row[0]
    if value is None:
        return frozenset()
    cursor = await connection.execute("SELECT version FROM schema_migrations ORDER BY version")
    rows = await cursor.fetchall()
    return frozenset(
        str(row["version"] if isinstance(row, dict) else row[0]) for row in rows
    )


async def apply_pending_migrations(
    connection: Any,
    migrations: tuple[PostgresMigration, ...],
) -> tuple[str, ...]:
    """Apply only migration versions not already recorded by the database."""

    applied = set(await applied_versions(connection))
    changed: list[str] = []
    for migration in migrations:
        if migration.version in applied:
            continue
        await connection.execute(migration.sql)
        applied.add(migration.version)
        changed.append(migration.version)
    return tuple(changed)
