from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from .core.config import get_settings
from .core.redis import get_redis
from .models import DeliveryReceipt
from .streams.publisher import publish_receipt
from .workers.queue_listener import start_listener

LOG = logging.getLogger("outbound")

app = FastAPI(title="Outbound Service", version="0.1.0")

_listener_task: Optional[asyncio.Task] = None


@app.on_event("startup")
async def _startup():
    global _listener_task
    settings = get_settings()
    redis_client = get_redis(settings)
    _listener_task = asyncio.create_task(start_listener(redis_client=redis_client, settings=settings))
    LOG.info("outbound listener started")


@app.on_event("shutdown")
async def _shutdown():
    global _listener_task
    if _listener_task:
        _listener_task.cancel()
        try:
            await _listener_task
        except Exception:
            pass


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/metrics")
async def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@app.post("/callbacks/{provider}")
async def provider_callback(provider: str, request: Request):
    """Optional endpoint for provider delivery receipts.

    This is intentionally generic; normalize upstream and emit to outbound:{provider}.
    Expected body may contain: event_id, session_id, provider_message_id, status, provider_error, trace_id.
    """

    settings = get_settings()
    redis_client = get_redis(settings)

    body: Dict[str, Any] = {}
    try:
        body = await request.json()
    except Exception:
        body = {}

    receipt = DeliveryReceipt(
        event_id=str(body.get("event_id", "")),
        session_id=str(body.get("session_id", "")),
        provider=provider,
        provider_message_id=str(body.get("provider_message_id", "")),
        status=str(body.get("status", "delivered")),
        timestamp=DeliveryReceipt.now_iso(),
        provider_error=body.get("provider_error"),
        trace_id=body.get("trace_id"),
    )

    await publish_receipt(redis_client, settings, receipt)
    return {"ok": True}
