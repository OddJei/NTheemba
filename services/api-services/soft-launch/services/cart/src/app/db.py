from __future__ import annotations

from collections.abc import AsyncIterator
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.app.config import get_database_url


class Base(DeclarativeBase):
    pass


_DATABASE_URL = get_database_url()
PG_SCHEMA = os.getenv("PG_SCHEMA", "").strip()
_connect_args: dict = {}
if PG_SCHEMA and _DATABASE_URL.startswith("postgres"):
    _connect_args = {"server_settings": {"search_path": PG_SCHEMA}}

engine = create_async_engine(_DATABASE_URL, future=True, connect_args=_connect_args)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
