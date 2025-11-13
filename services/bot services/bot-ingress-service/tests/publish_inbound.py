import asyncio
import json
import uuid
from datetime import datetime, timezone
import redis.asyncio as aioredis

INCOMING_STREAM = "incoming_messages"


async def main():
    r = aioredis.from_url("redis://localhost", decode_responses=True)

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
    await r.close()


if __name__ == '__main__':
    asyncio.run(main())
