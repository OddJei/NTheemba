import asyncio
import logging

from app.core.config import get_settings
from app.core.redis import get_redis
from app.workers.queue_listener import start_listener


async def main():
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    redis_client = get_redis(settings)
    try:
        await start_listener(redis_client, settings)
    finally:
        try:
            await redis_client.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
