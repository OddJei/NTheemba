from __future__ import annotations

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite+aiosqlite:///./ice.db"

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
Base = declarative_base()
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
