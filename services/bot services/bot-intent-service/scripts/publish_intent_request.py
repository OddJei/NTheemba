from __future__ import annotations

import os
import time
import uuid

from redis.asyncio import Redis


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value else default


async def main() -> None:
    redis_url = _env("REDIS_URL", "redis://localhost:6379/0")
    stream = _env("INTENT_REQUESTS_STREAM", "intent:requests")

    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    session_id = _env("SESSION_ID", f"sess_{uuid.uuid4().hex[:8]}")

    raw_text = _env("RAW_TEXT", "I want to buy 2 solar panels")
    bot_id = _env("BOT_ID", "bot_default")
    bot_type = _env("BOT_TYPE", "default")
    trace_id = _env("TRACE_ID", f"trace_{uuid.uuid4().hex[:10]}")

    payload = {
        "event_id": event_id,
        "session_id": session_id,
        "bot_id": bot_id,
        "bot_type": bot_type,
        "raw_text": raw_text,
        "trace_id": trace_id,
        # Keep this small. It’s ok if it’s absent.
        "enriched_meta": "{}",
        "attempts": "0",
        "published_at": str(int(time.time())),
    }

    redis = Redis.from_url(redis_url, decode_responses=True)
    try:
        msg_id = await redis.xadd(stream, payload)
    finally:
        await redis.aclose()

    print(f"published stream={stream} id={msg_id} event_id={event_id} session_id={session_id}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
