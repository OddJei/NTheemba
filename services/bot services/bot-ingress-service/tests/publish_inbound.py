import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
import redis.asyncio as aioredis

INCOMING_STREAM = "ingress:incoming"


async def main():
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = aioredis.from_url(redis_url, decode_responses=True)

    payload = {
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "message": "Hi, what can I do here?",
        "to": "ntb_default",
        "from": "097xxxxxxx",
        "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "meta": {"platform": "wa"},
    }

    entry_id = await r.xadd(INCOMING_STREAM, {"payload": json.dumps(payload)})
    print("Published to stream", INCOMING_STREAM, "id=", entry_id)
    await r.aclose()


if __name__ == '__main__':
    asyncio.run(main())
