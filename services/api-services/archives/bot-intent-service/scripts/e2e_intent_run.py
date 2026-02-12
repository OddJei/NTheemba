import asyncio
import json
import os
import uuid
import time
from datetime import datetime

from app.worker import worker_loop
from redis.asyncio import Redis

REQUESTS_STREAM = os.getenv('INTENT_REQUESTS_STREAM', 'intent:requests')
RESULTS_STREAM = os.getenv('INTENT_RESULTS_STREAM', 'intent:results')

async def publish_request(r: Redis, raw_text: str):
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    payload = {
        'event_id': event_id,
        'session_id': session_id,
        'raw_text': raw_text,
        'enriched_meta': json.dumps({'intent_required': True}),
        'attempts': '0',
    }
    msg_id = await r.xadd(REQUESTS_STREAM, payload)
    print('published', msg_id, event_id, session_id)
    return event_id, session_id

async def wait_for_response(r: Redis, event_id: str, timeout: int = 8):
    end = time.time() + timeout
    last = '$'
    while time.time() < end:
        resp = await r.xread({RESULTS_STREAM: last}, block=1000, count=10)
        if not resp:
            continue
        for _, messages in resp:
            for msg_id, fields in messages:
                last = msg_id
                payload = fields.get('payload') or fields
                try:
                    parsed = json.loads(payload) if isinstance(payload, str) else payload
                except Exception:
                    parsed = payload
                # parse event_id from payload
                ev = parsed.get('event_id') if isinstance(parsed, dict) else None
                if ev == event_id:
                    print('found response id=', msg_id)
                    print(json.dumps(parsed, indent=2))
                    return parsed
    return None

async def main():
    r = Redis.from_url(os.getenv('REDIS_URL','redis://localhost:6379/0'), decode_responses=True)
    raw_text = os.getenv('RAW_TEXT', 'i want 2 oranges and 4 apples delivered at riverside afternoon i will use mtn to pay')

    # start worker in background
    worker_task = asyncio.create_task(worker_loop())
    await asyncio.sleep(0.5)

    event_id, session_id = await publish_request(r, raw_text)
    resp = await wait_for_response(r, event_id, timeout=8)

    # teardown
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    await r.aclose()

    if not resp:
        print('no response found')

if __name__ == '__main__':
    asyncio.run(main())
