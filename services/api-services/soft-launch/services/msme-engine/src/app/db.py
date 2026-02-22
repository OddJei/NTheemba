from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_database_url


class Base(DeclarativeBase):
    pass


def create_engine() -> AsyncEngine:
    url = get_database_url()
    # If using asyncpg, set server_settings so asyncpg receives `server_settings`
    # which allows setting `search_path` per-connection.
    if url.startswith("postgresql+asyncpg://"):
        from .config import get_pg_schema

        schema = get_pg_schema()
        return create_async_engine(url, future=True, connect_args={"server_settings": {"search_path": schema}})

    # Special handling for SQLite in-memory to allow multiple connections
    # (tests set DATABASE_URL to sqlite+aiosqlite:///:memory:). Use a
    # shared-cache memory URI so create_all in startup is visible to other
    # connections used by request handling during tests.
    if url.startswith("sqlite+aiosqlite:///:memory:"):
        sqlite_uri = "sqlite+aiosqlite:///file:memdb1?mode=memory&cache=shared"
        return create_async_engine(sqlite_uri, future=True, connect_args={"uri": True})

    return create_async_engine(url, future=True)


engine = create_engine()
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
