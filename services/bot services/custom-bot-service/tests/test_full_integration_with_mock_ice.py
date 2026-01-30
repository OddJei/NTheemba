import asyncio
import json
import os
import socket

import pytest

import redis.asyncio as redis

from aiohttp import web


async def _start_mock_ice(port: int):
    app = web.Application()

    async def create_order(request):
        _ = await request.json()
        return web.json_response({"order_id": "ord_e2e", "status": "created"})

    async def trigger_payment(request):
        _ = await request.json()
        return web.json_response({"payment_id": "pay_e2e", "status": "initiated"})

    app.router.add_post("/ice/order/create", create_order)
    app.router.add_post("/ice/payment/trigger", trigger_payment)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    return runner, site


@pytest.mark.asyncio
async def test_worker_reads_stream_and_calls_ice():
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.from_url(url, decode_responses=True)
        await r.ping()
    except Exception:
        pytest.skip("Redis not available; skipping full integration test")

    # pick a free port for mock ICE
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    runner, site = await _start_mock_ice(port)
    ice_base = f"http://127.0.0.1:{port}"

    # patch runtime to use this ICE base for any IceClient instances
    from importlib import reload
    from app import runtime_engine as runtime_mod
    from app.ice_client import IceClient

    runtime_mod.IceClient = lambda *a, **k: IceClient(base_url=ice_base)

    # start worker loop
    from app.worker import process_loop

    worker_task = asyncio.create_task(process_loop(url))

    # wait briefly for worker to create consumer group
    await asyncio.sleep(0.3)

    # ensure clean state
    stream = os.getenv("CUSTOM_BOT_STREAM", "bot:lane:custom")
    reply_stream = os.getenv("CUSTOM_BOT_REPLY_STREAM", "reply:requests")
    audit_stream = os.getenv("CUSTOM_BOT_AUDIT_STREAM", "oob:audit")
    session_id = "int-session-1"
    await r.delete(reply_stream)
    await r.delete(audit_stream)
    await r.delete(f"oob:{session_id}")

    payload = {"event_id": "evt-int-1", "session_id": session_id, "raw_text": "2 apples"}

    # clear idempotency keys for the event so worker will process it
    await r.delete(f"idempotency:custombot:{payload['event_id']}:done")
    await r.delete(f"idempotency:custombot:{payload['event_id']}:lock")

    # publish to stream; worker should pick it up
    await r.xadd(stream, {"payload": json.dumps(payload)})

    # wait up to 5s for reply+audit
    ok = False
    for _ in range(50):
        await asyncio.sleep(0.1)
        replies = await r.xrange(reply_stream, min="-", max="+")
        audits = await r.xrange(audit_stream, min="-", max="+")
        if replies and audits:
            ok = True
            break

    # stop worker (cancel background task; do not await to avoid CancelledError propagation)
    worker_task.cancel()

    # cleanup mock server
    await runner.cleanup()

    assert ok, "Worker did not publish reply/audit entries within timeout"
