import asyncio
import json
import redis.asyncio as aioredis

STREAMS = [
    "resolved_payload_default",
    "resolved_payload_custom",
    "ingress_dlq",
]

async def main():
    r = aioredis.from_url("redis://localhost", decode_responses=True)
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
    await r.close()

if __name__ == '__main__':
    asyncio.run(main())
