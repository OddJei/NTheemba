"""Simple Redis stream worker for local testing.

Consumes from `BOT_LANE_PREFIX + BOT_NAME` stream and republishes a minimal envelope
to `outbound:request` so downstream services can be exercised in the compose network.

This is intentionally small and synchronous-friendly for local runs inside Docker.
"""

from __future__ import annotations

import os
import asyncio
import json
import logging
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger("custom_bot.stream_worker")
logging.basicConfig(level=logging.INFO)


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
BOT_LANE_PREFIX = os.getenv("BOT_LANE_PREFIX", "bot:lane:")
BOT_NAME = os.getenv("BOT_NAME", "custom")
OUTBOUND_STREAM = os.getenv("OUTBOUND_STREAM", "outbound:request")


async def handle_message(redis: aioredis.Redis, stream: str, message_id: str, fields: dict[str, Any]):
    logger.info("received message %s %s", stream, message_id)
    # Echo into outbound:request with minimal metadata for testing
    obj = {
        "from_stream": stream,
        "message_id": message_id,
        "fields": {k: (v.decode() if isinstance(v, bytes) else v) for k, v in fields.items()},
    }
    await redis.xadd(OUTBOUND_STREAM, {"payload": json.dumps(obj)})
    logger.info("published to %s: %s", OUTBOUND_STREAM, obj)


async def run():
    redis = aioredis.from_url(REDIS_URL)
    stream = f"{BOT_LANE_PREFIX}{BOT_NAME}"
    last_id = "0-0"
    logger.info("listening on stream %s -> outbound %s", stream, OUTBOUND_STREAM)
    try:
        while True:
            # XREAD blocking for 5s
            res = await redis.xread({stream: last_id}, block=5000, count=10)
            if not res:
                await asyncio.sleep(0.1)
                continue
            for sname, messages in res:
                for mid, fields in messages:
                    await handle_message(redis, sname.decode() if isinstance(sname, bytes) else sname, mid.decode() if isinstance(mid, bytes) else mid, fields)
                    last_id = mid
    finally:
        await redis.close()


if __name__ == "__main__":
    asyncio.run(run())
