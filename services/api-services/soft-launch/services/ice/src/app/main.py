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
from pydantic import BaseModel


class ConfirmRequest(BaseModel):
    order_id: str
    affiliate_id: str | None = None
    amount_minor: int | None = None
    correlation_id: str | None = None
    idempotency_key: str | None = None

app = FastAPI(title="ICE Service (Outbox)")
logger = logging.getLogger("ice")


def _require_internal_secret(request: Request) -> None:
    expected = (os.environ.get("OUTBOX_INTERNAL_SECRET") or "").strip()
    provided = (request.headers.get("X-Internal-Secret") or "").strip()
    if expected and (not provided or not secrets.compare_digest(provided, expected)):
        raise HTTPException(status_code=401, detail="invalid_internal_secret")


@app.get("/outbox/pending")
async def outbox_pending_ice(request: Request, batch_size: int = 50, db=Depends(get_db_session)):
    _require_internal_secret(request)
    q = select(Outbox).where(Outbox.status == "pending").order_by(Outbox.created_at).limit(int(batch_size))
    rows = (await db.execute(q)).scalars().all()
    out = []
    for r in rows:
        out.append({
            "id": r.id,
            "event_type": r.topic,
            "payload": r.payload,
            "dedupe_key": r.dedupe_key,
            "destination": r.destination,
            "attempts": r.attempts,
            "scheduled_at": (r.send_after.isoformat() if r.send_after else None),
            "correlation_id": None,
        })
    return out


@app.post("/outbox/ack")
async def outbox_ack_ice(request: Request, body: dict, db=Depends(get_db_session)):
    _require_internal_secret(request)
    ids = body.get("ids") or []
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="invalid_ids")
    q = select(Outbox).where(Outbox.id.in_(ids))
    rows = (await db.execute(q)).scalars().all()
    acked = []
    for r in rows:
        r.status = "sent"
        acked.append(r.id)
    if acked:
        await db.commit()
    return {"acked": acked}


@app.on_event("startup")
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
    out = Outbox(
        topic="ice.confirmed",
        dedupe_key=body.idempotency_key,
        destination="outbox-dispatcher",
        payload=payload,
        status="pending",
    )

    db.add(out)
    await db.flush()
    await db.commit()
    await db.refresh(out)

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

    return {"outbox_id": out.id}
