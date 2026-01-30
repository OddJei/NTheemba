from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config.settings import settings


# create async engine using the ASYNC_DATABASE_URL from settings
engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.ASYNC_DATABASE_URL.startswith("sqlite") else {},
    future=True,
)

# Async session factory
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()
