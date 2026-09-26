from pathlib import Path

import pytest

from ntheemba.infrastructure.postgres.migrations import (
    apply_pending_migrations,
    discover_migrations,
)


class FakeCursor:
    def __init__(self, *, row=None, rows=()):
        self._row = row
        self._rows = rows

    async def fetchone(self):
        return self._row

    async def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self, applied=()):
        self.applied = set(applied)
        self.executed: list[str] = []

    async def execute(self, sql: str):
        self.executed.append(sql)
        if "to_regclass" in sql:
            return FakeCursor(row={"schema_migrations": "schema_migrations" if self.applied else None})
        if sql.strip().startswith("SELECT version FROM schema_migrations"):
            return FakeCursor(rows=tuple({"version": item} for item in sorted(self.applied)))
        for migration in discover_migrations(Path("migrations/postgres")):
            if sql == migration.sql:
                self.applied.add(migration.version)
                break
        return FakeCursor()


def test_discover_migrations_has_unique_ordered_versions() -> None:
    migrations = discover_migrations(Path("migrations/postgres"))

    assert migrations
    assert len({item.version for item in migrations}) == len(migrations)
    assert migrations[-1].version == "012_business_capability_catalogue"
    assert [item.path.name for item in migrations] == sorted(item.path.name for item in migrations)


@pytest.mark.asyncio
async def test_migration_runner_skips_already_applied_versions() -> None:
    migrations = discover_migrations(Path("migrations/postgres"))
    connection = FakeConnection(applied={item.version for item in migrations[:-1]})

    changed = await apply_pending_migrations(connection, migrations)

    assert changed == ("012_business_capability_catalogue",)
    assert connection.applied == {item.version for item in migrations}


@pytest.mark.asyncio
async def test_migration_runner_is_idempotent_when_schema_is_current() -> None:
    migrations = discover_migrations(Path("migrations/postgres"))
    connection = FakeConnection(applied={item.version for item in migrations})

    changed = await apply_pending_migrations(connection, migrations)

    assert changed == ()
