import asyncio
import json
import os
import redis.asyncio as aioredis

STREAMS = [
    "ingress:resolved_payload",
    "bot:lane:default",
    "bot:lane:custom",
    "ingress:dlq",
]

async def main():
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = aioredis.from_url(redis_url, decode_responses=True)
    for s in STREAMS:
        print("\n==== Stream:", s)
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
    await r.aclose()

if __name__ == '__main__':
    asyncio.run(main())
