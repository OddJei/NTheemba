from typing import Optional
from redis.asyncio import Redis
from .config import Settings

_redis_client: Optional[Redis] = None


def get_redis(settings: Settings) -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=settings.redis_decode_responses)
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
