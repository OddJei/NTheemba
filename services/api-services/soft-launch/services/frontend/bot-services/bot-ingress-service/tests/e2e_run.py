import asyncio
import json
import os
import uuid
import time
from datetime import datetime, timezone
import redis.asyncio as aioredis

from app.core.config import get_settings
from app.workers.queue_listener import start_listener

INCOMING_STREAM = "ingress:incoming"
TARGET_STREAMS = ["ingress:resolved_payload", "bot:lane:default", "bot:lane:custom", "ingress:dlq"]

async def publish_test(r):
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
    return payload

async def dump_streams(r):
    for s in TARGET_STREAMS:
        print(f"\n==== Stream: {s}")
        try:
            entries = await r.xrange(s, count=10)
        except Exception as e:
            print("  Error reading stream:", e)
            continue
        if not entries:
            print("  (no entries)")
            continue
        for entry_id, fields in entries:
            payload = fields.get("payload") or fields
            try:
                parsed = json.loads(payload) if isinstance(payload, str) else payload
            except Exception:
                parsed = payload
            print(entry_id, "->", parsed)

async def main():
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = aioredis.from_url(redis_url, decode_responses=True)
    settings = get_settings()

    # Start listener in background
    listener_task = asyncio.create_task(start_listener(r, settings))
    await asyncio.sleep(0.8)

    # Publish inbound
    payload = await publish_test(r)

    # Wait for processing
    await asyncio.sleep(3)

    # Dump target streams
    await dump_streams(r)

    # Teardown
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass
    await r.aclose()

if __name__ == '__main__':
    asyncio.run(main())
