import os
import secrets
import asyncio
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import InvalidRequestError, DatabaseError
from sqlalchemy.orm.exc import StaleDataError
from typing import Optional, cast
import logging
from datetime import datetime
import httpx
from pydantic import BaseModel

# Pydantic models for request validation
from .schemas import (
    BotCreate,
    BotCreateResponse,
    CreateSessionReq,
    CreateSessionResponse,
    CreateEventReq,
    CreateEventResponse,
    StateTransitionRequest,
    StateCycleUpgradeRequest,
    EventUpdateRequest,
    EventResponse,
    EventListItem,
    SessionCycleResponse,
    SessionResponse,
    SessionListItem,
)

# local imports
from .db import async_engine, get_db_session, Base
from . import models, audit_client, security, jobs, events as event_publisher
from .helpers.outbox.outbox import create_outbox_row

logger = logging.getLogger("bot-session")

# Create FastAPI app
app = FastAPI(title="Bot-Session")

# Observability (optional): Sentry + Prometheus (guarded)
try:
    from .observability import instrument_app

    try:
        instrument_app(app)
    except Exception:
        logger.exception("instrument_app_failed")
except Exception:
    # Observability package or dependencies not present — continue silently.
    pass

# Paths to skip auth (exact or prefix)
_AUTH_SKIP_PATHS = ["/health", "/metrics", "/docs", "/openapi.json", "/events"]

# Consolidated events handler: support both create and upgrade topics
@app.post("/events/{topic}")
async def events_topic(topic: str, request: Request, body: dict, db: AsyncSession = Depends(get_db_session)):
    """Generic internal events ingress used by Outbox/dispatcher.

    Supports: `ice.cycle.created`, `ice.cycle.upgraded`.
    """
    _require_internal_secret(request)

    if topic not in ("ice.cycle.upgraded", "ice.cycle.created"):
        raise HTTPException(status_code=404, detail="unsupported_topic")

    payload = body or {}
    session_id = payload.get("session_id")
    if not session_id:
        # Defensive logging: record incoming payloads that lack session_id so
        # we can debug producers that send incomplete metadata.
        try:
            logger.warning("events_topic_missing_session_id", extra={"topic": topic, "payload": payload})
        except Exception:
            logger.warning("events_topic_missing_session_id_unserializable")
        raise HTTPException(status_code=400, detail="session_id_required")

    # Normalize fields depending on topic
    event_id = payload.get("event_id") or payload.get("id")
    snapshot = payload.get("snapshot") or {}
    if topic == "ice.cycle.upgraded":
        new_stage = payload.get("new_stage")
    else:
        new_stage = payload.get("cycle_state")

    # Fetch session
    res = await db.execute(select(models.Session).where(models.Session.id == session_id))
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="session_not_found")

    # Idempotency: if we've already processed this external event, return success
    if event_id:
        res_cycles = await db.execute(select(models.SessionStateCycle).where(models.SessionStateCycle.session_id == session_id))
        for c in res_cycles.scalars().all():
            meta = c.meta or {}
            if meta.get("origin_event_id") == event_id:
                return {"processed": True, "cycle_id": c.id}

    # For upgrade: close any open cycle; for create: don't close unless policy requires it
    if topic == "ice.cycle.upgraded":
        res_open = await db.execute(
            select(models.SessionStateCycle).where(models.SessionStateCycle.session_id == session_id, models.SessionStateCycle.completed_at == None)
        )
        open_cycle = res_open.scalars().first()
        if open_cycle:
            open_cycle.completed_at = datetime.utcnow()
            db.add(open_cycle)

    # Validate and create the new cycle
    # `new_stage` comes from an external event payload (unknown type). Ensure
    # it's a non-empty string before indexing the Enum so static checkers and
    # runtime errors are avoided.
    if new_stage is None or not isinstance(new_stage, str) or not new_stage:
        raise HTTPException(status_code=400, detail="invalid_new_stage")
    try:
        new_state = models.SessionState[new_stage]
    except KeyError:
        raise HTTPException(status_code=400, detail="invalid_new_stage")

    meta = {"origin_event_id": event_id, "snapshot": snapshot}
    new_cycle = models.SessionStateCycle(
        session_id=session_id,
        cycle_state=new_state,
        started_at=datetime.utcnow(),
        initiated_by_affiliate=False,
        affiliate_id=None,
        meta=meta,
    )
    db.add(new_cycle)

    # Merge snapshot into session.object_context under the new state key
    existing_context = s.object_context or {}
    existing_context[new_state.value] = {**(existing_context.get(new_state.value) or {}), **snapshot}
    s.object_context = existing_context
    s.state = new_state
    s.state_entered_at = datetime.utcnow()
    db.add(s)

    await db.commit()
    await db.refresh(new_cycle)
    await db.refresh(s)

    # Emit audit event for traceability (topic-specific event_type)
    evt_name = "cycle_created" if topic == "ice.cycle.created" else "cycle_upgraded"
    await audit_client.emit_audit(
        service="bot-session",
        event_type=evt_name,
        payload={"session_id": session_id, "new_state": new_state.value, "cycle_id": new_cycle.id, "origin_event_id": event_id},
        actor_id=cast(Optional[str], s.user_phone),
        entity_type="session",
        entity_id=session_id,
        metadata={"cycle_id": new_cycle.id},
    )

    return {"session_id": session_id, "new_state": new_state.value, "cycle_id": new_cycle.id}


def _require_internal_secret(request: Request) -> None:
    expected = (os.environ.get("OUTBOX_INTERNAL_SECRET") or "").strip()
    provided = (request.headers.get("X-Internal-Secret") or "").strip()
    if expected and (not provided or not secrets.compare_digest(provided, expected)):
        raise HTTPException(status_code=401, detail="invalid_internal_secret")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Require Bearer access tokens issued by msme-engine for all routes except health/metrics/docs.
    # Allow exact or prefix matches for skip paths (so internal event endpoints under `/events/...` are allowed)
    path = request.url.path
    if any(path == p or path.startswith(p + "/") for p in _AUTH_SKIP_PATHS):
        return await call_next(request)
    try:
        await security.require_access_token(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


async def resolve_bot_by_phone(db: AsyncSession, phone: str) -> Optional[models.Bot]:
    res = await db.execute(
        select(models.Bot).where(
            models.Bot.phone_number == phone,
            models.Bot.is_active == True,
        )
    )
    return res.scalar_one_or_none()


MSME_ENGINE_URL = os.getenv("MSME_ENGINE_URL", "http://127.0.0.1:8500")
AFFILIATE_ENGINE_BASE_URL = os.getenv("AFFILIATE_ENGINE_BASE_URL", "http://127.0.0.1:8510")
try:
    AFFILIATE_ENGINE_TIMEOUT_SECONDS = float(os.getenv("AFFILIATE_ENGINE_TIMEOUT_SECONDS", "3.0"))
except ValueError:
    AFFILIATE_ENGINE_TIMEOUT_SECONDS = 3.0


async def _msme_auth_lookup(user_phone: str) -> Optional[dict]:
    try:
        url = f"{MSME_ENGINE_URL}/auth/phone/{user_phone}"
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(url)
            if r.status_code == 200:
                return r.json()
    except Exception:
        return None
    return None


# `session_mode` is legacy; resolver removed.


async def startup():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    if os.getenv("DISABLE_CLEANUP_JOBS") != "1":
        try:
            jobs.schedule_cleanup(app)
            # schedule periodic sweeps for abandoned sessions and stuck cycles
            try:
                jobs.schedule_sweeps(app)
            except Exception:
                pass
        except Exception:
            pass


# Register startup handler without using the deprecated decorator.
app.add_event_handler("startup", startup)


@app.post("/bot/create", response_model=BotCreateResponse, responses={201: {"description": "Bot created", "content": {"application/json": {"example": {"bot_id": "bot_abc123", "phone_number": "+260971234567"}}}}})
async def bot_create(payload: BotCreate, db: AsyncSession = Depends(get_db_session)):
    phone = payload.phone_number
    if not phone:
        raise HTTPException(status_code=400, detail="phone_number required")
    existing = await resolve_bot_by_phone(db, phone)
    if existing:
        raise HTTPException(status_code=409, detail="bot already exists")

    bot = models.Bot(
        phone_number=phone,
        type=models.BotType[payload.type or "custom"],
        business_id=payload.business_id,
    )
    db.add(bot)
    await db.commit()
    await db.refresh(bot)
    
    # Emit audit event for bot creation
    await audit_client.emit_audit(
        service="bot-session",
        event_type="bot_created",
        payload={
            "bot_id": bot.id,
            "phone_number": bot.phone_number,
            "bot_type": bot.type.value,
            "business_id": bot.business_id,
        },
        entity_type="bot",
        entity_id=bot.id,
        metadata={"phone_number": bot.phone_number},
    )
    
    return JSONResponse(status_code=201, content={"bot_id": bot.id, "phone_number": bot.phone_number})


@app.get("/bot/by-phone/{phone}", response_model=BotCreateResponse, responses={200: {"description": "Bot lookup", "content": {"application/json": {"example": {"bot_id": "bot_abc123", "phone_number": "+260971234567"}}}}})
async def bot_by_phone(phone: str, db: AsyncSession = Depends(get_db_session)):
    bot = await resolve_bot_by_phone(db, phone)
    if not bot:
        raise HTTPException(status_code=404, detail="bot not found")
    return {"bot_id": bot.id, "phone_number": bot.phone_number}


@app.post("/session/create", response_model=CreateSessionResponse, responses={201: {"description": "Session created", "content": {"application/json": {"example": {"session_id": "sess_abc123", "status": "active", "reactivated": False, "last_event_id": None, "object_context": {}}}}}})
async def create_session(payload: CreateSessionReq, db: AsyncSession = Depends(get_db_session)):
    bot: Optional[models.Bot] = None
    if payload.bot_id:
        res = await db.execute(select(models.Bot).where(models.Bot.id == payload.bot_id))
        bot = res.scalar_one_or_none()
    elif payload.bot_phone:
        bot = await resolve_bot_by_phone(db, payload.bot_phone)
    if not bot:
        raise HTTPException(status_code=404, detail="bot not found")

    # session_mode legacy removed

    res = await db.execute(
        select(models.Session).where(
            models.Session.user_phone == payload.user_phone,
            models.Session.bot_id == bot.id,
            models.Session.platform == payload.platform,
        )
    )
    existing = res.scalar_one_or_none()

    if existing:
        prev_status = existing.status
        existing.status = models.SessionStatus.active
        # preserve previous state when reactivating
        if prev_status != models.SessionStatus.active:
            existing.reactivated_at = datetime.utcnow()
        existing.updated_at = datetime.utcnow()
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        session_obj = existing
        reactivated = True
    else:
        session_obj = models.Session(
            user_phone=payload.user_phone,
            bot_id=bot.id,
            business_id=payload.business_id,
            bot_type=bot.type,
            platform=payload.platform,
            status=models.SessionStatus.active,
            # SessionState init: start new sessions in the `chat` state by default.
            # This field represents the current logical stage of the user's session
            # (chat -> cart -> order -> payment -> delivery -> closed).
            state=models.SessionState.chat,
            # Timestamp when the session entered the current `state`.
            state_entered_at=datetime.utcnow(),
        )
        db.add(session_obj)
        await db.commit()
        await db.refresh(session_obj)
        reactivated = False

        # If affiliate info provided on create, record initial cycle with attribution
        cycle: Optional[models.SessionStateCycle] = None
        if payload.affiliate_id or payload.affiliate_metadata:
            # Initial SessionStateCycle: captures affiliate attribution at session creation.
            # This is recorded separately from the Session row so attribution is tracked per cycle.
            affiliate_metadata = payload.affiliate_metadata if isinstance(payload.affiliate_metadata, dict) else None
            incoming_context = affiliate_metadata.get("context") if affiliate_metadata else None
            cycle = _create_cycle(
                session_obj.id,
                session_obj.state,
                payload.affiliate_id,
                affiliate_metadata,
                incoming_context,
                None,
            )
            db.add(cycle)
            await db.flush()
            await _emit_affiliate_cycle_created(cycle, session_obj, db)
            await db.commit()
            await db.refresh(cycle)

    await audit_client.emit_audit(
        service="bot-session",
        event_type="session_created" if not reactivated else "session_reactivated",
        payload={
            "session_id": session_obj.id,
            "user_phone": payload.user_phone,
            "bot_id": bot.id,
            # session_mode removed
            "platform": payload.platform,
        },
        actor_id=payload.user_phone,
        entity_type="session",
        entity_id=session_obj.id,
        metadata={"business_id": payload.business_id, "bot_type": bot.type.value},
    )

    return JSONResponse(status_code=201, content={
        "session_id": session_obj.id,
        "status": session_obj.status.value,
        "reactivated": reactivated,
        "last_event_id": session_obj.last_event_id,
        "object_context": session_obj.object_context,
    })


@app.get("/session/{session_id}", response_model=SessionResponse, responses={200: {"description": "Session summary", "content": {"application/json": {"example": {"id": "sess_abc123", "user_phone": "+260971234567", "bot_id": "bot_abc", "platform": "whatsapp", "status": "active", "last_event_id": None, "state": "chat"}}}}})
async def get_session(session_id: str, db: AsyncSession = Depends(get_db_session)):
    res = await db.execute(select(models.Session).where(models.Session.id == session_id))
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "id": s.id,
        "user_phone": s.user_phone,
        "bot_id": s.bot_id,
        "platform": s.platform,
        "status": s.status.value,
        "last_event_id": s.last_event_id,
        "state": s.state.value if s.state is not None else None,
        "state_entered_at": s.state_entered_at,
    }


@app.get("/admin/session/{session_id}/full")
async def admin_session_full(session_id: str, request: Request, db: AsyncSession = Depends(get_db_session)):
    """Admin helper: return session + cycles + events for a session.

    Requires admin role in token payload (middleware already enforces auth).
    """
    token_payload = getattr(request.state, "token_payload", {}) or {}
    if token_payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin_required")

    res = await db.execute(select(models.Session).where(models.Session.id == session_id))
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="session not found")

    res_c = await db.execute(
        select(models.SessionStateCycle).where(models.SessionStateCycle.session_id == session_id).order_by(models.SessionStateCycle.started_at.asc())
    )
    cycles = [
        {
            "id": c.id,
            "cycle_state": c.cycle_state.value,
            "started_at": c.started_at,
            "completed_at": c.completed_at,
            "initiated_by_affiliate": c.initiated_by_affiliate,
            "affiliate_id": c.affiliate_id,
            "meta": c.meta,
        }
        for c in res_c.scalars().all()
    ]

    res_e = await db.execute(
        select(models.Event).where(models.Event.session_id == session_id).order_by(models.Event.created_at.asc())
    )
    events = [
        {"id": e.id, "event_type": e.event_type, "created_at": e.created_at, "payload_events": e.payload_events} for e in res_e.scalars().all()
    ]

    # Cross-service enrichment: fetch deliveries and orders from order-delivery service
    order_delivery_base = os.getenv("ORDER_DELIVERY_BASE_URL", "http://127.0.0.1:8520").rstrip("/")
    od_timeout = float(os.getenv("ORDER_DELIVERY_TIMEOUT_SECONDS", "3.0"))
    deliveries_info: list = []
    try:
        async with httpx.AsyncClient(timeout=od_timeout) as client:
            r = await client.get(f"{order_delivery_base}/delivery/user/{s.user_phone}")
            if r.status_code == 200:
                delivs = r.json() or []
                for d in delivs:
                    order_info = None
                    order_id = d.get("order_id") if isinstance(d, dict) else None
                    if order_id:
                        try:
                            ro = await client.get(f"{order_delivery_base}/orders/{order_id}")
                            if ro.status_code == 200:
                                order_info = ro.json()
                        except Exception:
                            order_info = None
                    deliveries_info.append({"delivery": d, "order": order_info})
    except Exception:
        deliveries_info = []

    return {
        "session": {"id": s.id, "user_phone": s.user_phone, "status": s.status.value, "state": s.state.value},
        "cycles": cycles,
        "events": events,
        "order_delivery": deliveries_info,
    }


@app.post("/session/{session_id}/close")
async def close_session(session_id: str, db: AsyncSession = Depends(get_db_session)):
    res = await db.execute(select(models.Session).where(models.Session.id == session_id))
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    if s.status == models.SessionStatus.closed:
        return {"session_id": s.id, "status": s.status.value}

    s.status = models.SessionStatus.closed
    s.closed_at = datetime.utcnow()
    if s.closed_at is not None and s.created_at is not None:
        try:
            closed_at_dt = cast(datetime, s.closed_at)
            created_at_dt = cast(datetime, s.created_at)
            s.duration_seconds = int((closed_at_dt - created_at_dt).total_seconds())
        except Exception:
            s.duration_seconds = None
    else:
        s.duration_seconds = None
    db.add(s)
    # complete any open cycles
    await db.commit()
    await db.refresh(s)
    await db.execute(
        select(models.SessionStateCycle).where(models.SessionStateCycle.session_id == s.id, models.SessionStateCycle.completed_at == None)
    )
    # Reuse existing helper behavior by calling event_create's internal logic not easily reachable here; instead mark cycles closed directly
    res_c = await db.execute(
        select(models.SessionStateCycle).where(models.SessionStateCycle.session_id == s.id, models.SessionStateCycle.completed_at == None)
    )
    for c in res_c.scalars().all():
        c.completed_at = datetime.utcnow()
        db.add(c)
    await db.commit()

    # Emit audit event for session closure
    await audit_client.emit_audit(
        service="bot-session",
        event_type="session_closed",
        payload={
            "session_id": s.id,
            "user_phone": s.user_phone,
            "bot_id": s.bot_id,
            "status": s.status.value,
            "duration_seconds": s.duration_seconds,
        },
        actor_id=cast(Optional[str], s.user_phone),
        entity_type="session",
        entity_id=s.id,
        metadata={"duration_seconds": s.duration_seconds},
    )

    return {"session_id": s.id, "status": s.status.value, "closed_at": s.closed_at}


# State transition request models moved to `schemas.py` for reuse and testing


def _extract_cycle_context(meta: Optional[dict]) -> dict:
    meta = meta or {}
    context = meta.get("context")
    return context if isinstance(context, dict) else {}


def _extract_affiliate_metadata(meta: Optional[dict]) -> Optional[dict]:
    meta = meta or {}
    affiliate_metadata = meta.get("affiliate_metadata")
    return affiliate_metadata if isinstance(affiliate_metadata, dict) else None


def _build_cycle_context(
    cycle_state: models.SessionState,
    incoming_context: Optional[dict],
    existing_context: Optional[dict],
) -> dict:
    incoming_context = incoming_context or {}
    existing_context = existing_context or {}

    if "user_text" in existing_context:
        user_text = existing_context.get("user_text")
    else:
        user_text = incoming_context.get("user_text", "")

    context = {"user_text": user_text}

    if cycle_state == models.SessionState.cart:
        cart_items = incoming_context.get("cart_items")
        if cart_items is None:
            cart_items = existing_context.get("cart_items") or []
        context["cart_items"] = cart_items
        context["checkout"] = True
    elif cycle_state == models.SessionState.order:
        order_id = incoming_context.get("order_id")
        if order_id is None:
            order_id = existing_context.get("order_id")
        context["order_id"] = order_id
        context["confirmed_order"] = True
    elif cycle_state == models.SessionState.payment:
        payment_method = incoming_context.get("payment_method")
        if payment_method is None:
            payment_method = existing_context.get("payment_method")
        context["payment_method"] = payment_method
        context["confirm_payment"] = True

    return context


def _build_cycle_meta(
    cycle_state: models.SessionState,
    incoming_context: Optional[dict],
    existing_meta: Optional[dict],
    affiliate_metadata: Optional[dict],
) -> dict:
    existing_context = _extract_cycle_context(existing_meta)
    context = _build_cycle_context(cycle_state, incoming_context, existing_context)
    meta = {"context": context}

    if affiliate_metadata is not None:
        meta["affiliate_metadata"] = affiliate_metadata
    else:
        existing_affiliate_metadata = _extract_affiliate_metadata(existing_meta)
        if existing_affiliate_metadata is not None:
            meta["affiliate_metadata"] = existing_affiliate_metadata

    return meta


def _resolve_initiated_by_affiliate(
    initiated_by_affiliate: Optional[bool],
    affiliate_id: Optional[str],
) -> bool:
    if initiated_by_affiliate is None:
        initiated_by_affiliate = True if affiliate_id else False

    if initiated_by_affiliate and not affiliate_id:
        raise HTTPException(status_code=400, detail="affiliate_id required when initiated_by_affiliate=true")
    if not initiated_by_affiliate and affiliate_id:
        raise HTTPException(status_code=400, detail="affiliate_id must be null when initiated_by_affiliate=false")

    return initiated_by_affiliate


async def _dispatch_to_affiliate_engine_cycle_created(*, payload: dict, correlation_id: str) -> bool:
    base = AFFILIATE_ENGINE_BASE_URL.rstrip("/")
    timeout = AFFILIATE_ENGINE_TIMEOUT_SECONDS

    headers: dict[str, str] = {"X-Correlation-Id": correlation_id}
    event_id = payload.get("event_id")
    if isinstance(event_id, str) and event_id:
        headers["X-Idempotency-Key"] = event_id

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{base}/events/session-cycle-created", json=payload, headers=headers)
    except httpx.RequestError:
        return False

    return r.status_code in (200, 201)


async def _emit_affiliate_cycle_created(cycle: models.SessionStateCycle, session: models.Session, db: Optional[AsyncSession] = None) -> None:
    # `cycle.initiated_by_affiliate` is a SQLAlchemy Column/Mapped field; avoid
    # using it in a boolean context so static type-checkers don't complain.
    if cast(Optional[bool], cycle.initiated_by_affiliate) is not True or cast(Optional[str], cycle.affiliate_id) is None:
        return

    # Guard optional datetimes and other mapped columns for static checkers
    started_at_dt = cast(Optional[datetime], cycle.started_at)
    occurred_at = started_at_dt.isoformat() if started_at_dt is not None else None

    payload = {
        "event_id": cycle.id,
        "event_type": "session_cycle_created",
        "occurred_at": occurred_at,
        "correlation_id": cycle.id,
        "producer": "bot-session",
        "affiliate_id": cast(Optional[str], cycle.affiliate_id),
        "session_id": cycle.session_id,
        "cycle_id": cycle.id,
        "cycle_state": cycle.cycle_state.value,
        "user_phone": cast(Optional[str], session.user_phone),
        "business_id": cast(Optional[str], session.business_id),
        "meta": cycle.meta,
    }

    # Prefer writing an Outbox row when a DB session is available so the
    # delivery is handled by the shared outbox dispatcher. Fall back to the
    # direct HTTP dispatch when no DB session is provided.
    if db is not None:
        try:
            destination = f"{AFFILIATE_ENGINE_BASE_URL.rstrip('/')}/events/session-cycle-created"
            schema = os.getenv("PG_SCHEMA") or "bot_session"
            table = f"{schema}.outbox_events"
            await create_outbox_row(db, "session_cycle_created", payload, destination=destination, correlation_id=cycle.id, idempotency_key=cycle.id, table=table)
        except Exception:
            logger.exception("create_outbox_row_failed")
    else:
        await _dispatch_to_affiliate_engine_cycle_created(payload=payload, correlation_id=cycle.id)


def _upgrade_cycle_meta(
    cycle_state: models.SessionState,
    incoming_context: Optional[dict],
    existing_meta: Optional[dict],
) -> dict:
    return _build_cycle_meta(cycle_state, incoming_context, existing_meta, None)


def _create_cycle(
    session_id: str,
    cycle_state: models.SessionState,
    affiliate_id: Optional[str],
    affiliate_metadata: Optional[dict],
    incoming_context: Optional[dict],
    existing_meta: Optional[dict],
) -> models.SessionStateCycle:
    meta = _build_cycle_meta(cycle_state, incoming_context, existing_meta, affiliate_metadata)
    return models.SessionStateCycle(
        session_id=session_id,
        cycle_state=cycle_state,
        started_at=datetime.utcnow(),
        initiated_by_affiliate=_resolve_initiated_by_affiliate(None, affiliate_id),
        affiliate_id=affiliate_id,
        meta=meta,
    )


async def lookup_cycle_state(session_id: str, db: AsyncSession) -> dict:
    res = await db.execute(
        select(models.SessionStateCycle)
        .where(models.SessionStateCycle.session_id == session_id)
        .order_by(models.SessionStateCycle.started_at.desc())
        .limit(1)
    )
    latest = res.scalars().first()
    if not latest:
        return {}
    return _extract_cycle_context(latest.meta)


@app.get("/admin/bots/overview")
async def bots_overview(db: AsyncSession = Depends(get_db_session)):
    """Expose bots grouped by active/inactive with session and cycle counts."""
    # Return per-bot summary: id, phone, is_active, session_count, cycle_count
    q = text(
        """
        SELECT b.id, b.phone_number, b.is_active,
          (SELECT COUNT(*) FROM sessions s WHERE s.bot_id = b.id) AS session_count,
          (SELECT COUNT(*) FROM session_state_cycles c JOIN sessions s2 ON c.session_id = s2.id WHERE s2.bot_id = b.id) AS cycle_count
        FROM bots b
        ORDER BY b.phone_number
        """
    )
    res = await db.execute(q)
    rows = [dict(r) for r in res.fetchall()]
    active = [r for r in rows if r.get("is_active")]
    inactive = [r for r in rows if not r.get("is_active")]
    return {"active": active, "inactive": inactive}


@app.get("/admin/bot/{bot_id}/sessions")
async def bot_sessions(bot_id: str, db: AsyncSession = Depends(get_db_session)):
    """Return session ids for a bot with counts of events and cycles."""
    q = text(
        """
        SELECT s.id, s.user_phone,
          (SELECT COUNT(*) FROM events e WHERE e.session_id = s.id) AS event_count,
          (SELECT COUNT(*) FROM session_state_cycles c WHERE c.session_id = s.id) AS cycle_count
        FROM sessions s
        WHERE s.bot_id = :bot_id
        ORDER BY s.created_at DESC
        """
    )
    res = await db.execute(q, {"bot_id": bot_id})
    return [dict(r) for r in res.fetchall()]


@app.get("/admin/session/{session_id}/detail")
async def session_detail(session_id: str, db: AsyncSession = Depends(get_db_session)):
    """Return latest cycle, previous cycle id, and cycle counts for a session."""
    # latest cycle
    latest_q = text(
        """
        SELECT id, cycle_state, started_at, completed_at, meta
        FROM session_state_cycles
        WHERE session_id = :session_id
        ORDER BY started_at DESC
        LIMIT 1
        """
    )
    latest = await db.execute(latest_q, {"session_id": session_id})
    latest_row = latest.fetchone()
    # previous cycle id
    prev_q = text(
        """
        SELECT id FROM session_state_cycles WHERE session_id = :session_id AND id != :latest_id ORDER BY started_at DESC LIMIT 1
        """
    )
    prev_id = None
    if latest_row:
        prev = await db.execute(prev_q, {"session_id": session_id, "latest_id": latest_row[0]})
        prv = prev.fetchone()
        prev_id = prv[0] if prv else None

    count_q = text("SELECT COUNT(*) FROM session_state_cycles WHERE session_id = :session_id")
    cnt = await db.execute(count_q, {"session_id": session_id})
    total_cycles = cnt.scalar_one()

    return {"latest": dict(latest_row) if latest_row else None, "previous_cycle_id": prev_id, "total_cycles": total_cycles}


@app.get("/admin/cycle/{cycle_id}")
async def cycle_detail(cycle_id: str, db: AsyncSession = Depends(get_db_session)):
    """Return cycle details and context."""
    q = text("SELECT id, session_id, cycle_state, started_at, completed_at, meta FROM session_state_cycles WHERE id = :cycle_id")
    res = await db.execute(q, {"cycle_id": cycle_id})
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="cycle not found")
    return dict(row)


@app.get("/cycle/{cycle_id}/context")
async def cycle_context(cycle_id: str, db: AsyncSession = Depends(get_db_session)):
    """Public endpoint: return the stored cycle context for a cycle id."""
    res = await db.execute(text("SELECT meta FROM session_state_cycles WHERE id = :id"), {"id": cycle_id})
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="cycle_not_found")
    meta = row[0] or {}
    context = _extract_cycle_context(meta)
    return {"cycle_id": cycle_id, "context": context}


@app.get("/cycle/{cycle_id}/context")
async def cycle_context(cycle_id: str, db: AsyncSession = Depends(get_db_session)):
    """Public endpoint: return extracted cycle context for a cycle id."""
    q = text("SELECT meta FROM session_state_cycles WHERE id = :cycle_id")
    res = await db.execute(q, {"cycle_id": cycle_id})
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="cycle not found")
    meta = row[0]
    return _extract_cycle_context(meta)


def validate_state_transition(current_state: models.SessionState, new_state_str: str, context: Optional[dict]) -> tuple[bool, str]:
    """Validate strict state progression and required context."""
    # Parse new state
    try:
        new_state = models.SessionState[new_state_str]
    except KeyError:
        return False, f"Invalid state: {new_state_str}"
    
    # Define valid transitions
    VALID_TRANSITIONS = {
        models.SessionState.chat: [models.SessionState.cart],
        models.SessionState.cart: [models.SessionState.order, models.SessionState.chat],
        models.SessionState.order: [models.SessionState.payment, models.SessionState.cart],
        models.SessionState.payment: [models.SessionState.delivery, models.SessionState.order],
        models.SessionState.delivery: [models.SessionState.closed],
        models.SessionState.closed: [],
    }
    
    # Check if transition is valid
    if new_state not in VALID_TRANSITIONS.get(current_state, []):
        return False, f"Invalid transition from {current_state.value} to {new_state.value}"
    
    # Validate required context per transition
    ctx = context or {}
    
    if new_state == models.SessionState.cart:
        # chat → cart requires selected items
        if not ctx.get("selected_items"):
            return False, "cart transition requires 'selected_items' in context"
    
    elif new_state == models.SessionState.order:
        # cart → order requires cart summary
        if not ctx.get("cart_summary"):
            return False, "order transition requires 'cart_summary' in context"
    
    elif new_state == models.SessionState.payment:
        # order → payment requires fulfillment + contact + total
        if not all(k in ctx for k in ["fulfillment", "contact", "order_total"]):
            return False, "payment transition requires 'fulfillment', 'contact', 'order_total' in context"
    
    elif new_state == models.SessionState.delivery:
        # payment → delivery requires payment success
        if ctx.get("payment_status") != "success" or not ctx.get("transaction_id"):
            return False, "delivery transition requires 'payment_status=success' and 'transaction_id' in context"
    
    elif new_state == models.SessionState.closed:
        # delivery → closed requires delivery confirmation and identifiers
        if (
            ctx.get("delivery_status") != "confirmed"
            or not ctx.get("delivery_code")
            or not ctx.get("order_id")
            or not ctx.get("payment_id")
        ):
            return False, "closed transition requires 'delivery_status=confirmed', 'delivery_code', 'order_id' and 'payment_id' in context"
    
    return True, ""


@app.post("/session/{session_id}/transition")
async def transition_session_state(
    session_id: str,
    payload: StateTransitionRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Transition session to new state with validation and structured context."""
    # Fetch session
    res = await db.execute(select(models.Session).where(models.Session.id == session_id))
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="session_not_found")
    
    if s.status == models.SessionStatus.closed:
        raise HTTPException(status_code=400, detail="session_already_closed")
    
    # Validate transition
    valid, error_msg = validate_state_transition(s.state, payload.new_state, payload.context)
    if not valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Parse new state
    new_state = models.SessionState[payload.new_state]
    
    # Complete current cycle
    res_cycle = await db.execute(
        select(models.SessionStateCycle).where(
            models.SessionStateCycle.session_id == session_id,
            models.SessionStateCycle.completed_at == None
        )
    )
    current_cycle = res_cycle.scalar_one_or_none()
    if current_cycle:
        current_cycle.completed_at = datetime.utcnow()
        db.add(current_cycle)
    
    # Update session state
    old_state = s.state
    s.state = new_state
    s.state_entered_at = datetime.utcnow()
    
    # Merge context into object_context
    if payload.context:
        existing_context = s.object_context or {}
        existing_context[new_state.value] = payload.context
        s.object_context = existing_context
    
    db.add(s)
    
    # Create new cycle for new state
    new_cycle = _create_cycle(
        session_id,
        new_state,
        payload.affiliate_id,
        None,
        payload.context,
        current_cycle.meta if current_cycle else None,
    )
    db.add(new_cycle)
    
    await db.flush()
    await _emit_affiliate_cycle_created(new_cycle, s, db)
    await db.commit()
    await db.refresh(s)
    await db.refresh(new_cycle)
    
    # Emit audit event
    await audit_client.emit_audit(
        service="bot-session",
        event_type="session_state_transition",
        payload={
            "session_id": session_id,
            "old_state": old_state.value,
            "new_state": new_state.value,
            "context_keys": list(payload.context.keys()) if payload.context else [],
        },
        actor_id=cast(Optional[str], s.user_phone),
        entity_type="session",
        entity_id=session_id,
        metadata={"transition": f"{old_state.value} → {new_state.value}"},
    )
    
    return {
        "session_id": session_id,
        "old_state": old_state.value,
        "new_state": new_state.value,
        "state_entered_at": s.state_entered_at,
        "cycle_id": new_cycle.id,
    }


@app.get("/session/{session_id}/context")
async def get_session_context(session_id: str, db: AsyncSession = Depends(get_db_session)):
    """Get structured context for a session."""
    res = await db.execute(select(models.Session).where(models.Session.id == session_id))
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="session_not_found")
    
    return {
        "session_id": session_id,
        "current_state": s.state.value,
        "object_context": s.object_context or {},
        "state_entered_at": s.state_entered_at,
    }


@app.patch("/session/{session_id}/context")
async def update_session_context(
    session_id: str,
    context: dict,
    db: AsyncSession = Depends(get_db_session)
):
    """Update structured context for current session state."""
    res = await db.execute(select(models.Session).where(models.Session.id == session_id))
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="session_not_found")
    
    # Merge context for current state
    existing_context = s.object_context or {}
    current_state_key = s.state.value
    existing_context[current_state_key] = {
        **(existing_context.get(current_state_key) or {}),
        **context,
    }
    s.object_context = existing_context
    db.add(s)
    await db.commit()
    
    return {
        "session_id": session_id,
        "current_state": s.state.value,
        "updated_context": existing_context[current_state_key],
    }


@app.get("/session/resolve")
async def resolve_session(
    user_phone: Optional[str] = None,
    bot_id: Optional[str] = None,
    platform: Optional[str] = None,
    affiliate_id: Optional[str] = None,
    affiliate_metadata: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    if not user_phone or not bot_id or not platform:
        raise HTTPException(status_code=400, detail="user_phone, bot_id and platform are required")

    res = await db.execute(
        select(models.Session).where(
            models.Session.user_phone == user_phone,
            models.Session.bot_id == bot_id,
            models.Session.platform == platform,
        )
    )
    s = res.scalar_one_or_none()
    if s:
        return {"session_id": s.id, "status": s.status.value}

    resb = await db.execute(select(models.Bot).where(models.Bot.id == bot_id))
    bot = resb.scalar_one_or_none()
    if not bot:
        raise HTTPException(status_code=404, detail="bot not found")

    # session_mode legacy removed; no resolver call
    new_s = models.Session(
        user_phone=user_phone,
        bot_id=bot.id,
        business_id=bot.business_id,
        bot_type=bot.type,
        platform=platform,
        status=models.SessionStatus.active,
        # SessionState init: new resolved sessions also start in `chat` by default.
        state=models.SessionState.chat,
        state_entered_at=datetime.utcnow(),
    )
    db.add(new_s)
    await db.flush()
    # record initial cycle if affiliate info present
    cycle: Optional[models.SessionStateCycle] = None
    if affiliate_id or affiliate_metadata:
        # Initial SessionStateCycle on session resolution when affiliate attribution
        # is provided by the resolver call.
        affiliate_metadata = affiliate_metadata if isinstance(affiliate_metadata, dict) else None
        incoming_context = affiliate_metadata.get("context") if affiliate_metadata else None
        cycle = _create_cycle(
            new_s.id,
            new_s.state,
            affiliate_id,
            affiliate_metadata,
            incoming_context,
            None,
        )
        db.add(cycle)
        await db.flush()
        await _emit_affiliate_cycle_created(cycle, new_s, db)
    await db.commit()
    await db.refresh(new_s)
    if cycle is not None:
        await db.refresh(cycle)
    return {"session_id": new_s.id, "status": new_s.status.value}


@app.get("/session/by-phone-platform/{user_phone}/{platform}", response_model=list[SessionListItem], responses={200: {"description": "Sessions by phone+platform", "content": {"application/json": {"example": [{"id": "sess_1", "bot_id": "bot_abc", "status": "active"}]}}}})
async def sessions_by_phone_platform(user_phone: str, platform: str, db: AsyncSession = Depends(get_db_session)):
    res = await db.execute(
        select(models.Session).where(
            models.Session.user_phone == user_phone,
            models.Session.platform == platform,
        )
    )
    rows = res.scalars().all()
    return [{"id": r.id, "bot_id": r.bot_id, "status": r.status.value} for r in rows]


@app.post("/event/create", response_model=CreateEventResponse, responses={201: {"description": "Event created", "content": {"application/json": {"example": {"event_id": "evt_123", "session_id": "sess_abc", "message_count": 1}}}}})
async def event_create(payload: CreateEventReq, db: AsyncSession = Depends(get_db_session)):
    # Protect critical updates: try DB-level row lock (SELECT FOR UPDATE) inside a transaction.
    # If the DB doesn't support it or a transaction can't be started, fall back to the
    # optimistic flush/commit path already in use.
    max_attempts = 3
    backoff = 0.05
    cycle: Optional[models.SessionStateCycle] = None
    for attempt in range(1, max_attempts + 1):
        try:
            try:
                # Attempt DB-level lock
                async with db.begin():
                    stmt = select(models.Session).where(models.Session.id == payload.session_id).with_for_update(nowait=True)
                    res_s = await db.execute(stmt)
                    session = res_s.scalar_one_or_none()
                    if not session:
                        raise HTTPException(status_code=404, detail="session not found")
                    # narrow type for static type-checkers
                    session = cast(models.Session, session)

                    # Now perform writes inside this transaction
                    message_count = 1
                    previous_turns: dict = {}
                    if payload.last_event_id:
                        res_last = await db.execute(select(models.Event).where(models.Event.id == payload.last_event_id))
                        last = res_last.scalar_one_or_none()
                        if last:
                            message_count = (last.message_count or 0) + 1
                            previous_turns["turn1"] = {
                                "id": last.id,
                                "event_type": last.event_type,
                                "payload_events": last.payload_events,
                                "message_count": last.message_count,
                            }
                            if last.last_event_id:
                                res_t2 = await db.execute(select(models.Event).where(models.Event.id == last.last_event_id))
                                t2 = res_t2.scalar_one_or_none()
                                if t2:
                                    previous_turns["turn2"] = {
                                        "id": t2.id,
                                        "event_type": t2.event_type,
                                        "payload_events": t2.payload_events,
                                        "message_count": t2.message_count,
                                    }
                                    if t2.last_event_id:
                                        res_t3 = await db.execute(select(models.Event).where(models.Event.id == t2.last_event_id))
                                        t3 = res_t3.scalar_one_or_none()
                                        if t3:
                                            previous_turns["turn3"] = {
                                                "id": t3.id,
                                                "event_type": t3.event_type,
                                                "payload_events": t3.payload_events,
                                                "message_count": t3.message_count,
                                            }

                    ev = models.Event(
                        session_id=payload.session_id,
                        user_phone=payload.user_phone or session.user_phone,
                        user_id=None,
                        bot_id=payload.bot_id,
                        last_event_id=payload.last_event_id,
                        message_count=message_count,
                        event_type=payload.event_type,
                        payload_events=payload.payload_events or {},
                        previous_turns=previous_turns or None,
                        status="created",
                    )
                    db.add(ev)
                    await db.flush()

                    session.last_event_id = ev.id
                    db.add(session)

                    # State transition mapping based on event_type.
                    # NOTE: when a transition occurs we create a new `SessionStateCycle` to
                    # represent the new logical stage. Any open cycle is completed first
                    # and its affiliate attribution is carried forward into the new cycle.
                    # This keeps attribution tied to the lifecycle of a specific session stage.
                    # See `SessionStateCycle` model for stored fields.
                    # State transition mapping based on event_type
                    transition_map = {
                        "enter_cart": models.SessionState.cart,
                        "add_to_cart": models.SessionState.cart,
                        "checkout": models.SessionState.order,
                        "payment_initiated": models.SessionState.payment,
                        "payment_success": models.SessionState.payment,
                        "delivery_initiated": models.SessionState.delivery,
                        "delivery_confirmed": models.SessionState.closed,
                    }

                    async def _fetch_and_complete_open_cycle():
                        res_c = await db.execute(
                            select(models.SessionStateCycle).where(models.SessionStateCycle.session_id == payload.session_id, models.SessionStateCycle.completed_at == None)
                        )
                        open_cycle = res_c.scalars().first()
                        if open_cycle:
                            # capture affiliate info before closing
                            aff_id = open_cycle.affiliate_id
                            prior_meta = open_cycle.meta or {}
                            open_cycle.completed_at = datetime.utcnow()
                            db.add(open_cycle)
                            return {
                                "affiliate_id": aff_id,
                                "affiliate_metadata": _extract_affiliate_metadata(prior_meta),
                                "context": _extract_cycle_context(prior_meta),
                                "meta": prior_meta,
                            }
                        return {"affiliate_id": None, "affiliate_metadata": None, "context": {}, "meta": None}

                    et = (payload.event_type or "")
                    if et in transition_map:
                        new_state = transition_map[et]
                        if session.state != new_state:
                            # On state transition: complete any open cycle and create
                            # a new SessionStateCycle for the `new_state`.
                            prior_aff = await _fetch_and_complete_open_cycle()
                            cycle = _create_cycle(
                                session.id,
                                new_state,
                                prior_aff.get("affiliate_id"),
                                None,
                                None,
                                prior_aff.get("meta"),
                            )
                            db.add(cycle)
                            await db.flush()
                            await _emit_affiliate_cycle_created(cycle, session, db)
                            session.state = new_state
                            session.state_entered_at = datetime.utcnow()
                            db.add(session)

                        if new_state == models.SessionState.closed:
                            session.status = models.SessionStatus.closed
                            session.closed_at = datetime.utcnow()
                            if session.closed_at is not None and session.created_at is not None:
                                try:
                                    closed_at_dt = cast(datetime, session.closed_at)
                                    created_at_dt = cast(datetime, session.created_at)
                                    session.duration_seconds = int((closed_at_dt - created_at_dt).total_seconds())
                                except Exception:
                                    session.duration_seconds = None
                            else:
                                session.duration_seconds = None
                            db.add(session)

                    # commit happens on context exit
                    await db.refresh(ev)
                    await audit_client.emit_audit(
                        service="bot-session",
                        event_type="event_created",
                        payload={
                            "event_id": ev.id,
                            "session_id": ev.session_id,
                            "event_type": payload.event_type,
                            "message_count": message_count,
                            "user_phone": ev.user_phone,
                        },
                        actor_id=cast(Optional[str], ev.user_phone),
                        entity_type="event",
                        entity_id=ev.id,
                        metadata={"session_id": ev.session_id, "bot_id": payload.bot_id},
                    )

                    try:
                        await event_publisher.publish_business_event(session.business_id or session.bot_id, {"event_id": ev.id, "session_id": session.id})
                    except Exception:
                        pass

                    return JSONResponse(status_code=201, content={"event_id": ev.id, "session_id": ev.session_id, "message_count": ev.message_count})
            except (InvalidRequestError, DatabaseError):
                # DB-level locking not supported / transaction couldn't be started; fall back to optimistic commit path
                # Ensure `session` is loaded for the optimistic path (was previously unbound)
                res_s = await db.execute(select(models.Session).where(models.Session.id == payload.session_id))
                session = res_s.scalar_one_or_none()
                if not session:
                    raise HTTPException(status_code=404, detail="session not found")
                # narrow type for static type-checkers
                session = cast(models.Session, session)
                message_count = 1
                previous_turns: dict = {}
                if payload.last_event_id:
                    res_last = await db.execute(select(models.Event).where(models.Event.id == payload.last_event_id))
                    last = res_last.scalar_one_or_none()
                    if last:
                        message_count = (last.message_count or 0) + 1
                        previous_turns["turn1"] = {
                            "id": last.id,
                            "event_type": last.event_type,
                            "payload_events": last.payload_events,
                            "message_count": last.message_count,
                        }
                        if last.last_event_id:
                            res_t2 = await db.execute(select(models.Event).where(models.Event.id == last.last_event_id))
                            t2 = res_t2.scalar_one_or_none()
                            if t2:
                                previous_turns["turn2"] = {
                                    "id": t2.id,
                                    "event_type": t2.event_type,
                                    "payload_events": t2.payload_events,
                                    "message_count": t2.message_count,
                                }
                                if t2.last_event_id:
                                    res_t3 = await db.execute(select(models.Event).where(models.Event.id == t2.last_event_id))
                                    t3 = res_t3.scalar_one_or_none()
                                    if t3:
                                        previous_turns["turn3"] = {
                                            "id": t3.id,
                                            "event_type": t3.event_type,
                                            "payload_events": t3.payload_events,
                                            "message_count": t3.message_count,
                                        }

                ev = models.Event(
                    session_id=payload.session_id,
                    user_phone=payload.user_phone or session.user_phone,
                    user_id=None,
                    bot_id=payload.bot_id,
                    last_event_id=payload.last_event_id,
                    message_count=message_count,
                    event_type=payload.event_type,
                    payload_events=payload.payload_events or {},
                    previous_turns=previous_turns or None,
                    status="created",
                )
                db.add(ev)
                await db.flush()

                session.last_event_id = ev.id
                db.add(session)

                # same transition handling as above
                transition_map = {
                    "enter_cart": models.SessionState.cart,
                    "add_to_cart": models.SessionState.cart,
                    "checkout": models.SessionState.order,
                    "payment_initiated": models.SessionState.payment,
                    "payment_success": models.SessionState.payment,
                    "delivery_initiated": models.SessionState.delivery,
                    "delivery_confirmed": models.SessionState.closed,
                }

                async def _fetch_and_complete_open_cycle():
                    res_c = await db.execute(
                        select(models.SessionStateCycle).where(models.SessionStateCycle.session_id == payload.session_id, models.SessionStateCycle.completed_at == None)
                    )
                    open_cycle = res_c.scalars().first()
                    if open_cycle:
                        aff_id = open_cycle.affiliate_id
                        prior_meta = open_cycle.meta or {}
                        open_cycle.completed_at = datetime.utcnow()
                        db.add(open_cycle)
                        return {
                            "affiliate_id": aff_id,
                            "affiliate_metadata": _extract_affiliate_metadata(prior_meta),
                            "context": _extract_cycle_context(prior_meta),
                            "meta": prior_meta,
                        }
                    return {"affiliate_id": None, "affiliate_metadata": None, "context": {}, "meta": None}

                et = (payload.event_type or "")
                if et in transition_map:
                    new_state = transition_map[et]
                    if session.state != new_state:
                        prior_aff = await _fetch_and_complete_open_cycle()
                        cycle = _create_cycle(
                            session.id,
                            new_state,
                            prior_aff.get("affiliate_id"),
                            None,
                            None,
                            prior_aff.get("meta"),
                        )
                        db.add(cycle)
                        await db.flush()
                        await _emit_affiliate_cycle_created(cycle, session, db)
                        session.state = new_state
                        session.state_entered_at = datetime.utcnow()
                        db.add(session)

                    if new_state == models.SessionState.closed:
                        session.status = models.SessionStatus.closed
                        session.closed_at = datetime.utcnow()
                        if session.closed_at is not None and session.created_at is not None:
                                try:
                                    closed_at_dt = cast(datetime, session.closed_at)
                                    created_at_dt = cast(datetime, session.created_at)
                                    session.duration_seconds = int((closed_at_dt - created_at_dt).total_seconds())
                                except Exception:
                                    session.duration_seconds = None
                        else:
                            session.duration_seconds = None
                        db.add(session)

                await db.commit()
                await db.refresh(ev)

                await audit_client.emit_audit(
                    service="bot-session",
                    event_type="event_created",
                    payload={
                        "event_id": ev.id,
                        "session_id": ev.session_id,
                        "event_type": payload.event_type,
                        "message_count": message_count,
                        "user_phone": ev.user_phone,
                    },
                    actor_id=cast(Optional[str], ev.user_phone),
                    entity_type="event",
                    entity_id=ev.id,
                    metadata={"session_id": ev.session_id, "bot_id": payload.bot_id},
                )

                try:
                    await event_publisher.publish_business_event(session.business_id or session.bot_id, {"event_id": ev.id, "session_id": session.id})
                except Exception:
                    pass

                return {"event_id": ev.id, "session_id": ev.session_id, "message_count": ev.message_count}

        except StaleDataError:
            # concurrent update detected; retry with small backoff
            if attempt == max_attempts:
                raise HTTPException(status_code=409, detail="concurrent_update")
            await asyncio.sleep(backoff * attempt)
            continue


@app.put("/event/{event_id}/update", response_model=CreateEventResponse)
async def event_update(event_id: str, body: "EventUpdateRequest", db: AsyncSession = Depends(get_db_session)):
    res = await db.execute(select(models.Event).where(models.Event.id == event_id))
    ev = res.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="event not found")

    upd = body.updated_fields if getattr(body, "updated_fields", None) is not None else None
    if upd:
        ev.updated_fields = {**(ev.updated_fields or {}), **upd}

    if getattr(body, "append_payload_event", None):
        payload = ev.payload_events or {}
        events = payload.get("events", [])
        events.append(body.append_payload_event)
        payload["events"] = events
        ev.payload_events = payload

    if getattr(body, "status", None) is not None:
        ev.status = body.status

    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return {"event_id": ev.id, "status": ev.status}


@app.get("/event/{event_id}", response_model=EventResponse, responses={200: {"description": "Event detail", "content": {"application/json": {"example": {"id": "evt_123", "session_id": "sess_abc", "event_type": "enter_cart", "payload_events": {}, "previous_turns": [], "message_count": 1, "status": "created"}}}}})
async def event_get(event_id: str, db: AsyncSession = Depends(get_db_session)):
    res = await db.execute(select(models.Event).where(models.Event.id == event_id))
    ev = res.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="event not found")
    return {
        "id": ev.id,
        "session_id": ev.session_id,
        "event_type": ev.event_type,
        "payload_events": ev.payload_events,
        "previous_turns": ev.previous_turns,
        "message_count": ev.message_count,
        "status": ev.status,
    }


@app.get("/event/session/{session_id}", response_model=list[EventListItem], responses={200: {"description": "Events for session", "content": {"application/json": {"example": [{"id": "evt_1", "event_type": "enter_cart", "created_at": "2026-02-17T12:00:00Z", "message_count": 1}]}}}})
async def events_for_session(session_id: str, db: AsyncSession = Depends(get_db_session)):
    res = await db.execute(
        select(models.Event)
        .where(models.Event.session_id == session_id)
        .order_by(models.Event.created_at.desc())
    )
    rows = res.scalars().all()
    return [{"id": r.id, "event_type": r.event_type, "created_at": r.created_at, "message_count": r.message_count} for r in rows]


@app.get("/session/{session_id}/cycles", response_model=list[SessionCycleResponse], responses={200: {"description": "Session cycles", "content": {"application/json": {"example": [{"id": "cycle_1", "cycle_state": "cart", "started_at": "2026-02-17T12:00:00Z", "completed_at": None, "initiated_by_affiliate": True, "affiliate_id": "aff_123", "meta": {}}]}}}})
async def session_cycles(session_id: str, db: AsyncSession = Depends(get_db_session)):
    res = await db.execute(
        select(models.SessionStateCycle).where(models.SessionStateCycle.session_id == session_id).order_by(models.SessionStateCycle.started_at.asc())
    )
    rows = res.scalars().all()
    return [
        {
            "id": r.id,
            "cycle_state": r.cycle_state.value,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
            "initiated_by_affiliate": r.initiated_by_affiliate,
            "affiliate_id": r.affiliate_id,
            "meta": r.meta,
        }
        for r in rows
    ]


@app.post("/session/{session_id}/cycle/{cycle_id}/upgrade")
async def upgrade_cycle_by_id(
    session_id: str,
    cycle_id: str,
    payload: StateCycleUpgradeRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Upgrade a specific open cycle identified by session_id+cycle_id to a new state.

    This allows targeted upgrades when clients reference a particular cycle.
    """
    # Fetch session
    res = await db.execute(select(models.Session).where(models.Session.id == session_id))
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="session_not_found")

    # Fetch cycle
    res_c = await db.execute(select(models.SessionStateCycle).where(models.SessionStateCycle.id == cycle_id))
    c = res_c.scalar_one_or_none()
    if not c or c.session_id != session_id:
        raise HTTPException(status_code=404, detail="cycle_not_found")

    if c.completed_at is not None:
        raise HTTPException(status_code=400, detail="cycle_already_completed")

    # Validate transition from the cycle's current state
    valid, err = validate_state_transition(c.cycle_state, payload.new_state, payload.context)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    # Complete the targeted cycle
    c.completed_at = datetime.utcnow()
    db.add(c)

    # Create new cycle carrying affiliate attribution
    new_state = models.SessionState[payload.new_state]
    new_cycle = _create_cycle(
        session_id,
        new_state,
        c.affiliate_id,
        None,
        payload.context,
        c.meta,
    )
    db.add(new_cycle)

    # Update session state if needed
    if s.state != new_state:
        s.state = new_state
        s.state_entered_at = datetime.utcnow()
        db.add(s)

    await db.flush()
    await _emit_affiliate_cycle_created(new_cycle, s, db)
    await db.commit()
    await db.refresh(new_cycle)
    await db.refresh(s)

    await audit_client.emit_audit(
        service="bot-session",
        event_type="cycle_upgraded",
        payload={"session_id": session_id, "old_cycle_id": c.id, "new_cycle_id": new_cycle.id, "new_state": new_state.value},
        actor_id=cast(Optional[str], s.user_phone),
        entity_type="session",
        entity_id=session_id,
        metadata={"cycle_id": new_cycle.id},
    )

    return {"session_id": session_id, "new_state": new_state.value, "cycle_id": new_cycle.id}


@app.get("/event/phone/{user_phone}")
async def events_by_phone(user_phone: str, db: AsyncSession = Depends(get_db_session)):
    res = await db.execute(
        select(models.Event)
        .where(models.Event.user_phone == user_phone)
        .order_by(models.Event.created_at.desc())
    )
    rows = res.scalars().all()
    return [{"id": r.id, "session_id": r.session_id, "event_type": r.event_type} for r in rows]


@app.get("/health")
async def health():
    return {"status": "ok"}

