from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.app import config


class Base(DeclarativeBase):
    pass


_schema = config.get_pg_schema()
_connect_args = None
if _schema and config.get_database_url().startswith("postgres"):
    # asyncpg doesn't support libpq 'options=-csearch_path=...' parameters.
    # Use server_settings to set search_path instead.
    _connect_args = {"server_settings": {"search_path": _schema}}

engine = create_async_engine(
    config.get_database_url(),
    echo=False,
    future=True,
    connect_args=(_connect_args or {}),
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
