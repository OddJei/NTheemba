from __future__ import annotations

from collections.abc import AsyncIterator

from redis.asyncio import Redis

from .config import settings


class RedisClient:
    """Singleton-style async Redis client factory."""

    _client: Redis | None = None

    @classmethod
    async def get_client(cls) -> Redis:
        if cls._client is None:
            cls._client = Redis.from_url(settings.redis.url, decode_responses=True)
        return cls._client

    @classmethod
    async def close(cls) -> None:
        if cls._client is not None:
            await cls._client.close()
            cls._client = None

    @classmethod
    async def context(cls) -> AsyncIterator[Redis]:
        client = await cls.get_client()
        try:
            yield client
        finally:
            pass
