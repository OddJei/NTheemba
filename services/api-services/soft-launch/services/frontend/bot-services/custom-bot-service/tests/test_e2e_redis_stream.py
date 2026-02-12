import asyncio
import json
import os

import pytest

import redis.asyncio as redis

from app import processor


@pytest.mark.asyncio
async def test_e2e_writes_reply_and_audit_from_stream():
    """Real Redis integration test.

    Requires a running Redis instance. Set `REDIS_URL` env or default to redis://localhost:6379/0.
    The test will be skipped if Redis is not reachable.
    """
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.from_url(url, decode_responses=True)
        await r.ping()
    except Exception:
        pytest.skip("Redis not available at REDIS_URL; skipping end-to-end Redis integration test")

    # cleanup streams and oob key for a fresh run
    session_id = "e2e-session-1"
    reply_stream = os.getenv("CUSTOM_BOT_REPLY_STREAM", "reply:requests")
    audit_stream = os.getenv("CUSTOM_BOT_AUDIT_STREAM", "oob:audit")
    oob_key = f"oob:{session_id}"

    await r.delete(reply_stream)
    await r.delete(audit_stream)
    await r.delete(oob_key)

    payload = {"event_id": "evt-e2e-1", "session_id": session_id, "raw_text": "2 apples"}
    # clear any idempotency keys for the event
    await r.delete(f"idempotency:custombot:{payload['event_id']}:done")
    await r.delete(f"idempotency:custombot:{payload['event_id']}:lock")

    # call processor.handle_entry directly, simulating a stream entry
    await processor.handle_entry(r, stream="bot:lane:custom", entry_id="1-0", data={"payload": json.dumps(payload)})

    # small delay to ensure async writes complete
    await asyncio.sleep(0.1)

    # verify reply stream has an entry
    replies = await r.xrange(reply_stream, min="-", max="+")
    audits = await r.xrange(audit_stream, min="-", max="+")

    assert len(replies) >= 1, "No reply entries written to reply stream"
    assert len(audits) >= 1, "No audit entries written to audit stream"

    # inspect most recent reply payload
    last_id, last_fields = replies[-1]
    last_payload = json.loads(last_fields.get("payload") or "{}")
    assert last_payload.get("session_id") == session_id

    # inspect most recent audit payload
    aid, afields = audits[-1]
    apayload = json.loads(afields.get("payload") or "{}")
    assert apayload.get("session_id") == session_id
