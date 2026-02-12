from __future__ import annotations

import asyncio
import logging
import uvicorn
from fastapi import FastAPI

from .worker import run_worker
from .exporter import start_exporter
import redis.asyncio as redis
from .audit_client import install_audit_log_forwarding

logger = logging.getLogger("custom_bot.main")

app = FastAPI(title="custom-bot-service")


@app.get("/health")
async def health():
    return {"status": "ok"}


async def _start_background_tasks() -> None:
    loop = asyncio.get_event_loop()
    # start worker in background
    loop.create_task(run_worker())
    # start simple exporter if Redis is available
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url, decode_responses=True)
        loop.create_task(start_exporter(r))
    except Exception:
        logger.exception("failed_starting_exporter")
    # install audit log forwarding so logs are sent to audit service
    try:
        install_audit_log_forwarding(service="custom-bot-service")
    except Exception:
        logger.exception("install_audit_log_forwarding_failed")


def start_api():
    # configure logging
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.create_task(_start_background_tasks())
    uvicorn.run(app, host="0.0.0.0", port=8055)


if __name__ == "__main__":
    start_api()
