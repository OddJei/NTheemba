from __future__ import annotations

import os
import asyncio
import logging
from typing import List

import httpx
import asyncpg
import json
from fastapi import FastAPI


app = FastAPI(title="Outbox Dispatcher (Poller)")
logger = logging.getLogger("outbox_dispatcher")
logging.basicConfig(level=os.environ.get("OUTBOX_LOG_LEVEL", "INFO"))


BATCH_SIZE = int(os.environ.get("OUTBOX_BATCH_SIZE", "50"))
OUTBOX_SERVICES = os.environ.get(
    "OUTBOX_SERVICES",
    "http://localhost:8500,http://localhost:8560,http://localhost:8590,http://localhost:8510,http://localhost:8100",
).split(",")
POLL_INTERVAL = float(os.environ.get("OUTBOX_POLL_INTERVAL_SECONDS", "5"))
INTERNAL_SECRET = os.environ.get("OUTBOX_INTERNAL_SECRET", "")
MAX_ATTEMPTS = int(os.environ.get("OUTBOX_MAX_ATTEMPTS", "5"))


USE_DB = os.environ.get("OUTBOX_USE_DB", "1") in ("1", "true", "yes")
# prefer explicit DATABASE_DSN, else fall back to DATABASE_URL from compose/.env
raw_dsn = os.environ.get("DATABASE_DSN") or os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_ASYNC")
if raw_dsn is None:
    # default local postgres for dev
    raw_dsn = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
# convert SQLAlchemy-style async URL to asyncpg-friendly DSN
if raw_dsn.startswith("postgresql+asyncpg://"):
    DATABASE_DSN = raw_dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
else:
    DATABASE_DSN = raw_dsn

# The outbox table to read/update. Should be schema.table (e.g. bot_session.outbox_events)
OUTBOX_TABLE = os.environ.get("OUTBOX_TABLE", "bot_session.outbox_events")


def _validate_table_name(name: str) -> str:
    # basic validation to avoid SQL injection via env var
    if not name or ";" in name or "--" in name:
        raise ValueError("invalid OUTBOX_TABLE")
    # allow only letters, digits, underscore and dot
    import re

    if not re.match(r"^[A-Za-z0-9_]+\.[A-Za-z0-9_]+$", name):
        raise ValueError("OUTBOX_TABLE must be in format schema.table")
    return name


OUTBOX_TABLE = _validate_table_name(OUTBOX_TABLE)


async def fetch_pending_from(service_base: str):
    """If OUTBOX_USE_DB is enabled, read directly from the configured outbox table. Otherwise poll service endpoint."""
    if USE_DB:
        try:
            conn = await asyncpg.connect(DATABASE_DSN)
            # ensure optional response columns exist so updates won't fail
            await conn.execute(f"ALTER TABLE {OUTBOX_TABLE} ADD COLUMN IF NOT EXISTS last_response jsonb;")
            await conn.execute(f"ALTER TABLE {OUTBOX_TABLE} ADD COLUMN IF NOT EXISTS last_status_code integer;")
            await conn.execute(f"ALTER TABLE {OUTBOX_TABLE} ADD COLUMN IF NOT EXISTS last_attempted_at timestamptz;")

            rows = await conn.fetch(
                f"""
                SELECT id, topic, destination, payload, headers, producer, correlation_id, dedupe_key
                FROM {OUTBOX_TABLE}
                WHERE status = 'pending' AND (send_after IS NULL OR send_after <= now())
                ORDER BY created_at ASC
                LIMIT $1
                """,
                BATCH_SIZE,
            )
            await conn.close()
            pending = []
            for r in rows:
                pending.append(
                    {
                        "id": str(r["id"]),
                        "topic": r.get("topic"),
                        "destination": r.get("destination"),
                        "payload": r.get("payload"),
                        "headers": r.get("headers"),
                        "producer": r.get("producer"),
                        "correlation_id": r.get("correlation_id"),
                        "dedupe_key": r.get("dedupe_key"),
                    }
                )
            return pending
        except Exception as e:
            logger.exception("fetch_pending_db_error", extra={"error": str(e)})
            return []

    # fallback: poll service endpoint
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
    if USE_DB:
        try:
            conn = await asyncpg.connect(DATABASE_DSN)
            await conn.executemany(
                f"""
                UPDATE {OUTBOX_TABLE}
                SET status = 'sent', attempts = attempts + 1, updated_at = now()
                WHERE id = $1
                """,
                [(i,) for i in ids],
            )
            await conn.close()
            return True
        except Exception as e:
            logger.exception("ack_db_error", extra={"error": str(e)})
            return False

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
    # Use dedupe key as idempotency (only set when present and coerce to str)
    dedupe_key = event.get("dedupe_key")
    if dedupe_key is not None:
        headers["X-Idempotency-Key"] = str(dedupe_key)

    status_code = None
    body = None
    ok = False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(dest, json=payload, headers=headers)
            status_code = r.status_code
            try:
                body = r.json()
            except Exception:
                body = r.text
            ok = status_code in (200, 201)
    except Exception as exc:
        logger.exception("dispatch_http_error", extra={"dest": dest, "error": str(exc)})
        body = "dispatch_exception"

    # If using DB mode, update attempts/status and record last response
    if USE_DB:
        try:
            conn = await asyncpg.connect(DATABASE_DSN)
            # persist JSON body as jsonb when possible
            resp_val = json.dumps(body) if not isinstance(body, (str, bytes)) else body
            if ok:
                await conn.execute(
                    f"""
                    UPDATE {OUTBOX_TABLE}
                    SET status = 'sent', attempts = attempts + 1, last_response = $2::jsonb, last_status_code = $3, last_attempted_at = now(), updated_at = now()
                    WHERE id = $1
                    """,
                    event.get("id"),
                    resp_val,
                    status_code,
                )
            else:
                await conn.execute(
                    f"""
                    UPDATE {OUTBOX_TABLE}
                    SET attempts = attempts + 1, last_response = $2::jsonb, last_status_code = $3, last_attempted_at = now(), updated_at = now(),
                        status = CASE WHEN attempts + 1 >= $4 THEN 'failed' ELSE status END
                    WHERE id = $1
                    """,
                    event.get("id"),
                    resp_val,
                    status_code,
                    MAX_ATTEMPTS,
                )
            await conn.close()
        except Exception:
            logger.exception("ack_update_error")

    return ok


async def poll_loop():
    while True:
        if USE_DB:
            # Read once from DB and dispatch
            pending = await fetch_pending_from("db")
            if pending:
                for ev in pending:
                    ok = await dispatch_event(ev)
                    if not ok:
                        logger.warning("dispatch_failed", extra={"event": ev.get("id")})
        else:
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


@app.get("/health")
async def health():
    return {"status": "ok"}

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
