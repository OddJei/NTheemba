from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_database_url


class Base(DeclarativeBase):
    pass


def create_engine() -> AsyncEngine:
    return create_async_engine(get_database_url(), future=True)


engine = create_engine()
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_db_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
