"""Apply ordered Ntheemba PostgreSQL migrations safely and idempotently."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ntheemba.infrastructure.asyncio_compat import use_windows_selector_event_loop_policy
from ntheemba.infrastructure.postgres.migrations import (
    apply_pending_migrations,
    discover_migrations,
)


async def migrate(dsn: str, migrations_dir: Path) -> tuple[str, ...]:
    """Open PostgreSQL and apply only versions not already recorded."""

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as error:  # pragma: no cover - runtime environment guard
        raise RuntimeError("psycopg is required to apply PostgreSQL migrations") from error

    migrations = discover_migrations(migrations_dir)
    async with await psycopg.AsyncConnection.connect(
        dsn,
        autocommit=True,
        row_factory=dict_row,
    ) as connection:
        changed = await apply_pending_migrations(connection, migrations)
    for version in changed:
        print(f"Applied {version}")
    if not changed:
        print("PostgreSQL schema already up to date")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="PostgreSQL connection string")
    parser.add_argument(
        "--migrations",
        default="migrations/postgres",
        type=Path,
        help="Directory containing ordered .sql files",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="List ordered migration versions without connecting to PostgreSQL",
    )
    args = parser.parse_args()
    migrations = discover_migrations(args.migrations)
    if args.plan:
        for migration in migrations:
            print(f"{migration.version}\t{migration.path.name}")
        return
    if not args.dsn:
        parser.error("--dsn is required unless --plan is used")
    use_windows_selector_event_loop_policy()
    asyncio.run(migrate(args.dsn, args.migrations))


if __name__ == "__main__":
    main()
