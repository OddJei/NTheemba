import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Use async DB URL. If a sync sqlite URL is provided, translate to aiosqlite URL.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")

PG_SCHEMA = os.getenv("PG_SCHEMA", "").strip()

_connect_args: dict = {}
if PG_SCHEMA and DATABASE_URL.startswith("postgres"):
    # asyncpg doesn't support libpq 'options=-csearch_path=...' URL params.
    _connect_args = {"server_settings": {"search_path": PG_SCHEMA}}

async_engine = create_async_engine(DATABASE_URL, echo=False, future=True, connect_args=_connect_args)
AsyncSessionLocal = sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def get_db_session():
    async with AsyncSessionLocal() as session:
        yield session
