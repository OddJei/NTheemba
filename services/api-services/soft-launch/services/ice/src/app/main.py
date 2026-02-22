from __future__ import annotations

import os
import secrets
import asyncio
import logging
from datetime import datetime, timezone
from typing import List

import httpx
import json
from fastapi import FastAPI, Request, HTTPException, Depends
from sqlalchemy import select
from src.app.db import Base, engine, get_db_session
from src.app.models import Outbox
import uuid
from libs.outbox.outbox import create_outbox_row
from pydantic import BaseModel


class ConfirmRequest(BaseModel):
    order_id: str
    affiliate_id: str | None = None
    amount_minor: int | None = None
    correlation_id: str | None = None
    idempotency_key: str | None = None


class UpdateStageRequest(BaseModel):
    cycle_id: str | None = None
    new_stage: str
    snapshot: dict | None = None
    event_id: str | None = None
    idempotency_key: str | None = None
    initiated_by: str | None = None

from contextlib import asynccontextmanager

logger = logging.getLogger("ice")


async def _post_to_bot_session(topic: str, payload: dict) -> None:
    """Best-effort synchronous fast-path: POST the Outbox payload to bot-session internal ingress.

    This must never make the ICE transaction non-durable: failures are logged and ignored.
    """
    bot_base = os.environ.get("BOT_SESSION_URL")
    internal_secret = os.environ.get("OUTBOX_INTERNAL_SECRET")
    if not bot_base:
        return
    try:
        url = bot_base.rstrip("/") + f"/events/{topic}"
        headers = {}
        if internal_secret:
            headers["X-Internal-Secret"] = internal_secret
        event_id = payload.get("event_id") or payload.get("id")
        if event_id:
            headers["X-Idempotency-Key"] = str(event_id)
        async with httpx.AsyncClient(timeout=2.0) as c:
            await c.post(url, json=payload, headers=headers)
    except Exception as e:
        logger.warning("bot_session_fastpost_failed", extra={"error": str(e), "topic": topic})


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def lifespan(app):
    await create_tables()
    yield


app = FastAPI(title="ICE Service (Outbox)", lifespan=lifespan)


def _require_internal_secret(request: Request) -> None:
    expected = (os.environ.get("OUTBOX_INTERNAL_SECRET") or "").strip()
    provided = (request.headers.get("X-Internal-Secret") or "").strip()
    if expected and (not provided or not secrets.compare_digest(provided, expected)):
        raise HTTPException(status_code=401, detail="invalid_internal_secret")


@app.get("/outbox/pending")
async def outbox_pending_ice(request: Request, batch_size: int = 50, db=Depends(get_db_session)):
    _require_internal_secret(request)
    sql = """
    SELECT id, topic, payload::text as payload, dedupe_key, destination, attempts, scheduled_at, correlation_id
    FROM public.outbox
    WHERE status = 'pending'
    ORDER BY created_at ASC
    LIMIT :limit
    """
    from sqlalchemy import text
    res = await db.execute(text(sql), {"limit": int(batch_size)})
    rows = res.fetchall()
    out = []
    for r in rows:
        try:
            payload = json.loads(r.payload) if r.payload else {}
        except Exception:
            payload = {}
        out.append({
            "id": str(r.id),
            "event_type": r.topic,
            "payload": payload,
            "dedupe_key": r.dedupe_key,
            "destination": r.destination,
            "attempts": int(r.attempts or 0),
            "scheduled_at": r.scheduled_at,
            "correlation_id": r.correlation_id,
        })
    return out


@app.post("/sessions/{session_id}/update_stage")
async def session_update_stage(request: Request, session_id: str, body: UpdateStageRequest, db=Depends(get_db_session)):
    """Upgrade a session/cycle stage and persist an Outbox row atomically.

    Writes an `ice.cycle.upgraded` outbox row inside the same DB transaction that
    performs the authoritative state change.
    """
    _require_internal_secret(request)

    payload = {
        "session_id": session_id,
        "cycle_id": body.cycle_id,
        "new_stage": body.new_stage,
        "snapshot": body.snapshot or {},
        "event_id": body.event_id,
        "initiated_by": body.initiated_by,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Prefer delivering directly to bot-session when configured; otherwise use the dispatcher service name.
    bot_base = os.environ.get("BOT_SESSION_URL")
    destination = bot_base.rstrip("/") + f"/events/ice.cycle.upgraded" if bot_base else "outbox-dispatcher"
    out_id = str(uuid.uuid4())
    await create_outbox_row(
        db,
        "ice.cycle.upgraded",
        payload,
        id=out_id,
        destination=destination,
        idempotency_key=body.idempotency_key or body.event_id,
        correlation_id=body.event_id,
        producer="ice",
    )
    # Persist in-session (caller manages commit)
    await db.flush()

    # Optional compatibility mirroring to Redis (best-effort)
    try:
        if os.environ.get("OUTBOX_MIRROR_REDIS") == "1" and os.environ.get("REDIS_URL"):
            try:
                import redis.asyncio as aioredis

                redis_url = os.environ.get("REDIS_URL")
                r = aioredis.from_url(redis_url)
                await r.xadd("ice:cycle.upgraded", {"data": json.dumps(payload)})
            except Exception as e:
                logger.warning("redis_mirror_failed", extra={"error": str(e)})
    except Exception:
        pass

    await db.commit()
    await db.refresh(out)
    # Optional compatibility mirroring to Redis (best-effort)
    try:
        if os.environ.get("OUTBOX_MIRROR_REDIS") == "1" and os.environ.get("REDIS_URL"):
            try:
                import redis.asyncio as aioredis

                redis_url = os.environ.get("REDIS_URL")
                r = aioredis.from_url(redis_url)
                await r.xadd("ice:cycle.upgraded", {"data": json.dumps(payload)})
            except Exception as e:
                logger.warning("redis_mirror_failed", extra={"error": str(e)})
    except Exception:
        pass

    # Best-effort synchronous fast-path to bot-session (after Outbox commit)
    try:
        await _post_to_bot_session("ice.cycle.upgraded", payload)
    except Exception:
        pass

    return {"outbox_id": out.id}


@app.post("/sessions/{session_id}/create_cycle")
async def session_create_cycle(request: Request, session_id: str, body: UpdateStageRequest, db=Depends(get_db_session)):
    """Create a SessionStateCycle and persist an Outbox row atomically.

    Writes an `ice.cycle.created` outbox row and fast-posts to bot-session.
    """
    _require_internal_secret(request)

    payload = {
        "session_id": session_id,
        "cycle_id": body.cycle_id,
        "cycle_state": body.new_stage,
        "snapshot": body.snapshot or {},
        "event_id": body.event_id,
        "idempotency_key": body.idempotency_key,
        "initiated_by": body.initiated_by,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Prefer delivering directly to bot-session when configured; otherwise use the dispatcher service name.
    bot_base = os.environ.get("BOT_SESSION_URL")
    destination = bot_base.rstrip("/") + f"/events/ice.cycle.created" if bot_base else "outbox-dispatcher"
    out_id = str(uuid.uuid4())
    await create_outbox_row(
        db,
        "ice.cycle.created",
        payload,
        id=out_id,
        destination=destination,
        idempotency_key=body.idempotency_key or body.event_id,
        correlation_id=body.event_id,
        producer="ice",
    )
    await db.flush()

    # Optional Redis mirror
    try:
        if os.environ.get("OUTBOX_MIRROR_REDIS") == "1" and os.environ.get("REDIS_URL"):
            try:
                import redis.asyncio as aioredis

                redis_url = os.environ.get("REDIS_URL")
                r = aioredis.from_url(redis_url)
                await r.xadd("ice:cycle.created", {"data": json.dumps(payload)})
            except Exception as e:
                logger.warning("redis_mirror_failed", extra={"error": str(e)})
    except Exception:
        pass

    await db.commit()
    await db.refresh(out)

    # Fast-post
    try:
        await _post_to_bot_session("ice.cycle.created", payload)
    except Exception:
        pass

    return {"outbox_id": out.id}


@app.post("/outbox/ack")
async def outbox_ack_ice(request: Request, body: dict, db=Depends(get_db_session)):
    _require_internal_secret(request)
    ids = body.get("ids") or []
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="invalid_ids")
    from sqlalchemy import text
    now = datetime.utcnow()
    for _id in ids:
        await db.execute(text("UPDATE public.outbox SET status = 'sent', updated_at = :now WHERE id = :id"), {"now": now, "id": _id})
    await db.commit()
    return {"acked": ids}


# startup handled by lifespan; `create_tables()` kept for tests to call directly


@app.post("/sessions/{session_id}/confirm")
async def session_confirm(request: Request, session_id: str, body: ConfirmRequest, db=Depends(get_db_session)):
    """Confirm a session/order and persist an Outbox row atomically.

    This endpoint writes an `ice.confirmed` outbox row inside the DB transaction
    so downstream delivery via the dispatcher can be driven from the Outbox.
    """
    _require_internal_secret(request)

    payload = {
        "session_id": session_id,
        "order_id": body.order_id,
        "affiliate_id": body.affiliate_id,
        "amount_minor": body.amount_minor,
    }

    # Create Outbox row using the service ORM so schema differences are respected.
    out_id = str(uuid.uuid4())
    await create_outbox_row(
        db,
        "ice.confirmed",
        payload,
        id=out_id,
        destination="outbox-dispatcher",
        idempotency_key=body.idempotency_key,
        producer="ice",
    )
    await db.flush()
    await db.commit()

    # Optional compatibility: mirror the event to Redis stream for legacy consumers.
    # Enabled when OUTBOX_MIRROR_REDIS=1 and REDIS_URL is set. Failure is best-effort.
    try:
        if os.environ.get("OUTBOX_MIRROR_REDIS") == "1" and os.environ.get("REDIS_URL"):
            try:
                import redis.asyncio as aioredis

                redis_url = os.environ.get("REDIS_URL")
                r = aioredis.from_url(redis_url)
                # xadd expects mapping; store payload as JSON under 'data'
                await r.xadd("ice:confirmed", {"data": json.dumps(payload)})
            except Exception as e:
                logger.warning("redis_mirror_failed", extra={"error": str(e)})
    except Exception:
        # top-level safety: never fail the confirm API because mirroring failed
        pass

    # Best-effort synchronous fast-path to bot-session (after Outbox commit)
    try:
        await _post_to_bot_session("ice.confirmed", payload)
    except Exception:
        pass

    return {"outbox_id": out.id}
