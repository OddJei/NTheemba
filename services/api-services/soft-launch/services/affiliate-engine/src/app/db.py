from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_database_url, get_pg_schema


class Base(DeclarativeBase):
    pass


def create_engine() -> AsyncEngine:
    url = get_database_url()
    # If using asyncpg, set server_settings so asyncpg receives `server_settings`
    # instead of an unsupported `options` kwarg.
    if url.startswith("postgresql+asyncpg://"):
        schema = get_pg_schema()
        return create_async_engine(url, future=True, connect_args={"server_settings": {"search_path": schema}})

    return create_async_engine(url, future=True)


engine = create_engine()
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_db_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
