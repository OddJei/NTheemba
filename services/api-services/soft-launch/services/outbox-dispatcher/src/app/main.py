from __future__ import annotations

import os
import asyncio
import logging
import time
from typing import List

import httpx
from fastapi import FastAPI

app = FastAPI(title="Outbox Dispatcher (Poller)")
logger = logging.getLogger("outbox_dispatcher")

OUTBOX_SERVICES = os.environ.get(
    "OUTBOX_SERVICES",
    "http://localhost:8500,http://localhost:8560,http://localhost:8590,http://localhost:8510,http://localhost:8100",
).split(",")
BATCH_SIZE = int(os.environ.get("OUTBOX_BATCH_SIZE", "50"))
POLL_INTERVAL = float(os.environ.get("OUTBOX_POLL_INTERVAL_SECONDS", "5"))
INTERNAL_SECRET = os.environ.get("OUTBOX_INTERNAL_SECRET", "")
MAX_ATTEMPTS = int(os.environ.get("OUTBOX_MAX_ATTEMPTS", "5"))


async def fetch_pending_from(service_base: str):
    url = f"{service_base.rstrip('/')}/outbox/pending"
    headers = {"X-Internal-Secret": INTERNAL_SECRET}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, params={"batch_size": BATCH_SIZE}, headers=headers)
            if r.status_code == 200:
                return r.json()
            logger.warning("fetch_pending_failed", extra={"service": service_base, "status": r.status_code})
    except Exception as e:
        logger.exception("fetch_pending_error", extra={"service": service_base, "error": str(e)})
    return []


async def ack_ids(service_base: str, ids: List[str]):
    url = f"{service_base.rstrip('/')}/outbox/ack"
    headers = {"X-Internal-Secret": INTERNAL_SECRET}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json={"ids": ids}, headers=headers)
            return r.status_code == 200
    except Exception:
        return False


async def dispatch_event(event: dict):
    dest = event.get("destination")
    if not dest:
        return False
    payload = event.get("payload") or {}
    headers = {"X-Internal-Secret": INTERNAL_SECRET}
    # Use dedupe key as idempotency
    if event.get("dedupe_key"):
        headers["X-Idempotency-Key"] = event.get("dedupe_key")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(dest, json=payload, headers=headers)
            return r.status_code in (200, 201)
    except Exception:
        return False


async def poll_loop():
    while True:
        for svc in OUTBOX_SERVICES:
            pending = await fetch_pending_from(svc)
            if not pending:
                continue
            ack_list = []
            for ev in pending:
                ok = await dispatch_event(ev)
                if ok:
                    ack_list.append(ev.get("id"))
                else:
                    logger.warning("dispatch_failed", extra={"event": ev.get("id")})
            if ack_list:
                await ack_ids(svc, ack_list)
        await asyncio.sleep(POLL_INTERVAL)


@app.on_event("startup")
async def startup_event():
    # Start poll loop in background
    asyncio.create_task(poll_loop())


@app.post("/run_once")
async def run_once():
    """Run a single poll across configured services and return a summary."""
    summary = {"dispatched": 0, "acked": 0, "failed": 0}
    for svc in OUTBOX_SERVICES:
        pending = await fetch_pending_from(svc)
        if not pending:
            continue
        ack_list = []
        for ev in pending:
            ok = await dispatch_event(ev)
            if ok:
                ack_list.append(ev.get("id"))
                summary["dispatched"] += 1
            else:
                summary["failed"] += 1
        if ack_list:
            ok = await ack_ids(svc, ack_list)
            if ok:
                summary["acked"] += len(ack_list)
    return summary
