from __future__ import annotations

from redis.asyncio import Redis

from .config import Settings


def get_redis(settings: Settings) -> Redis:
    return Redis.from_url(settings.redis.url, decode_responses=settings.redis.decode_responses)
