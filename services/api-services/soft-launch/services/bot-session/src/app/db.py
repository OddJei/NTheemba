import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base
from typing import AsyncIterator

try:
    # SQLAlchemy >=1.4.39 / 2.0 exposes `async_sessionmaker`
    from sqlalchemy.ext.asyncio import async_sessionmaker  # type: ignore
    _HAS_ASYNC_SESSIONMAKER = True
except Exception:
    # Older SQLAlchemy 1.4.x installs may not expose `async_sessionmaker`.
    # Fall back to the classic `sessionmaker` configured to produce AsyncSession.
    from sqlalchemy.orm import sessionmaker  # type: ignore
    _HAS_ASYNC_SESSIONMAKER = False

# Use async DB URL. If a sync sqlite URL is provided, translate to aiosqlite URL.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")

PG_SCHEMA = os.getenv("PG_SCHEMA", "").strip()

_connect_args: dict = {}
if PG_SCHEMA and DATABASE_URL.startswith("postgres"):
    # asyncpg doesn't support libpq 'options=-csearch_path=...' URL params.
    _connect_args = {"server_settings": {"search_path": PG_SCHEMA}}

async_engine = create_async_engine(DATABASE_URL, echo=False, future=True, connect_args=_connect_args)

# Create a session factory that yields `AsyncSession` instances.
if _HAS_ASYNC_SESSIONMAKER:
    AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(bind=async_engine, expire_on_commit=False)  # type: ignore
else:
    AsyncSessionLocal = sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore
Base = declarative_base()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
