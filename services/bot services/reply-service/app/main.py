from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from .core.config import get_settings
from .core.redis import get_redis
from .workers.queue_listener import start_listener

LOG = logging.getLogger("reply")

app = FastAPI(title="Reply Service", version="0.1.0")

_listener_task: Optional[asyncio.Task] = None


@app.on_event("startup")
async def _startup():
    global _listener_task
    logging.basicConfig(level=logging.INFO)

    settings = get_settings()
    if not settings.worker_enabled:
        LOG.info("reply worker disabled")
        return

    redis_client = get_redis(settings)
    _listener_task = asyncio.create_task(start_listener(redis_client=redis_client, settings=settings))
    LOG.info("reply listener started")


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
