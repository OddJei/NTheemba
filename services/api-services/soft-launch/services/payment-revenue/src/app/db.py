from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.app.config import get_database_url, get_pg_schema


class Base(DeclarativeBase):
    pass


_db_url = get_database_url()
_schema = get_pg_schema()

connect_args = None
if _schema and _db_url.startswith("postgresql"):
    # asyncpg uses server_settings for things like search_path; it does NOT accept libpq-style 'options'.
    connect_args = {"server_settings": {"search_path": _schema}}

engine = create_async_engine(_db_url, echo=False, connect_args=connect_args or {})
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session():
    async with SessionLocal() as session:
        yield session
