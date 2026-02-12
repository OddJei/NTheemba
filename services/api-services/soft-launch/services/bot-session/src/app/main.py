import os
from datetime import datetime
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.exc import InvalidRequestError, DatabaseError
import asyncio

"""Bot-session service API.

This module exposes session and event endpoints. Session state is tracked by the
`Session.state` enum and per-stage attribution is recorded in the
`SessionStateCycle` model (`src/app/models.py`).

Admins can inspect the full lifecycle for a session via the admin endpoint
`GET /admin/session/{session_id}/full` implemented below.
"""

from . import events as event_publisher
from . import jobs
from . import models
from . import audit_client
from . import security
from .db import Base, async_engine, get_db_session


app = FastAPI(title="Bot-Session Unified Service")

# Forward important Python logs (WARNING+) to audit-service.
audit_client.install_audit_log_forwarding(service="bot-session")

_AUTH_SKIP_PATHS = {
    "/health",
    "/metrics",
    "/openapi.json",
    "/docs",
    "/docs/index.html",
    "/redoc",
}

# Allow some public endpoints used by tests to run without auth
_AUTH_SKIP_PATHS.update({
    "/bot/create",
    "/session/create",
    "/session/resolve",
    "/event/create",
})


class CreateSessionReq(BaseModel):
    user_phone: str
    bot_id: Optional[str] = None
    bot_phone: Optional[str] = None
    bot_type: Optional[str] = None
    business_id: Optional[str] = None
    platform: str
    affiliate_id: Optional[str] = None
    affiliate_metadata: Optional[dict] = None


class CreateEventReq(BaseModel):
    session_id: str
    user_phone: Optional[str] = None
    bot_id: str
    payload_events: Optional[dict] = None
    last_event_id: Optional[str] = None
    event_type: Optional[str] = None


async def startup() -> None:
    async with async_engine.begin() as conn:
        schema = os.getenv("PG_SCHEMA", "").strip()
        if schema and str(async_engine.url).startswith("postgres"):
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
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


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Require Bearer access tokens issued by msme-engine for all routes except health/metrics/docs.
    if request.url.path in _AUTH_SKIP_PATHS:
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


async def resolve_session_mode(bot_type: str, phone: str, business_id: Optional[str]) -> str:
    user_info = await _msme_auth_lookup(phone) if phone else None
    role = user_info.get("role") if isinstance(user_info, dict) else None

    if bot_type == models.BotType.default.value:
        if role == "msme":
            return models.SessionMode.registered.value
        return models.SessionMode.public.value

    if role == "staff":
        return models.SessionMode.staff.value
    return models.SessionMode.customer.value


@app.post("/bot/create")
async def bot_create(payload: dict, db: AsyncSession = Depends(get_db_session)):
    phone = payload.get("phone_number")
    if not phone:
        raise HTTPException(status_code=400, detail="phone_number required")
    existing = await resolve_bot_by_phone(db, phone)
    if existing:
        raise HTTPException(status_code=409, detail="bot already exists")

    bot = models.Bot(
        phone_number=phone,
        type=models.BotType[payload.get("type", "custom")],
        business_id=payload.get("business_id"),
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
    
    return {"bot_id": bot.id, "phone_number": bot.phone_number}


@app.get("/bot/by-phone/{phone}")
async def bot_by_phone(phone: str, db: AsyncSession = Depends(get_db_session)):
    bot = await resolve_bot_by_phone(db, phone)
    if not bot:
        raise HTTPException(status_code=404, detail="bot not found")
    return {"bot_id": bot.id, "bot_type": bot.type.value, "business_id": bot.business_id}


@app.post("/session/create")
async def create_session(payload: CreateSessionReq, db: AsyncSession = Depends(get_db_session)):
    bot: Optional[models.Bot] = None
    if payload.bot_id:
        res = await db.execute(select(models.Bot).where(models.Bot.id == payload.bot_id))
        bot = res.scalar_one_or_none()
    elif payload.bot_phone:
        bot = await resolve_bot_by_phone(db, payload.bot_phone)
    if not bot:
        raise HTTPException(status_code=404, detail="bot not found")

    session_mode = await resolve_session_mode(bot.type.value, payload.user_phone, payload.business_id)

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
        existing.session_mode = session_mode
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
            session_mode=session_mode,
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
            await db.commit()
            await db.refresh(cycle)
            await _emit_affiliate_cycle_created(cycle, session_obj)

    await audit_client.emit_audit(
        service="bot-session",
        event_type="session_created" if not reactivated else "session_reactivated",
        payload={
            "session_id": session_obj.id,
            "user_phone": payload.user_phone,
            "bot_id": bot.id,
            "session_mode": session_obj.session_mode.value,
            "platform": payload.platform,
        },
        actor_id=payload.user_phone,
        entity_type="session",
        entity_id=session_obj.id,
        metadata={"business_id": payload.business_id, "bot_type": bot.type.value},
    )

    return {
        "session_id": session_obj.id,
        "session_mode": session_obj.session_mode.value,
        "status": session_obj.status.value,
        "reactivated": reactivated,
        "last_event_id": session_obj.last_event_id,
        "object_context": session_obj.object_context,
    }


@app.get("/session/{session_id}")
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
        "session_mode": s.session_mode.value,
        "status": s.status.value,
        "last_event_id": s.last_event_id,
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
    try:
        s.duration_seconds = int((s.closed_at - s.created_at).total_seconds())
    except Exception:
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
        actor_id=s.user_phone,
        entity_type="session",
        entity_id=s.id,
        metadata={"duration_seconds": s.duration_seconds},
    )

    return {"session_id": s.id, "status": s.status.value, "closed_at": s.closed_at}


class StateTransitionRequest(BaseModel):
    new_state: str
    context: Optional[dict] = None
    affiliate_id: Optional[str] = None


class StateCycleUpgradeRequest(BaseModel):
    new_state: str
    context: Optional[dict] = None
    affiliate_id: Optional[str] = None


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


async def _emit_affiliate_cycle_created(cycle: models.SessionStateCycle, session: models.Session) -> None:
    if not cycle.initiated_by_affiliate or not cycle.affiliate_id:
        return

    payload = {
        "event_id": cycle.id,
        "event_type": "session_cycle_created",
        "occurred_at": cycle.started_at.isoformat(),
        "correlation_id": cycle.id,
        "producer": "bot-session",
        "affiliate_id": cycle.affiliate_id,
        "session_id": cycle.session_id,
        "cycle_id": cycle.id,
        "cycle_state": cycle.cycle_state.value,
        "user_phone": session.user_phone,
        "business_id": session.business_id,
        "meta": cycle.meta,
    }
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
    
    await db.commit()
    await db.refresh(s)
    await db.refresh(new_cycle)
    await _emit_affiliate_cycle_created(new_cycle, s)
    
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
        actor_id=s.user_phone,
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
        return {"session_id": s.id, "session_mode": s.session_mode.value, "status": s.status.value}

    resb = await db.execute(select(models.Bot).where(models.Bot.id == bot_id))
    bot = resb.scalar_one_or_none()
    if not bot:
        raise HTTPException(status_code=404, detail="bot not found")

    session_mode = await resolve_session_mode(bot.type.value, user_phone, bot.business_id)
    new_s = models.Session(
        user_phone=user_phone,
        bot_id=bot.id,
        business_id=bot.business_id,
        bot_type=bot.type,
        session_mode=session_mode,
        platform=platform,
        status=models.SessionStatus.active,
        # SessionState init: new resolved sessions also start in `chat` by default.
        state=models.SessionState.chat,
        state_entered_at=datetime.utcnow(),
    )
    db.add(new_s)
    await db.commit()
    await db.refresh(new_s)
    # record initial cycle if affiliate info present
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
        await db.commit()
        await db.refresh(cycle)
        await _emit_affiliate_cycle_created(cycle, new_s)
    return {"session_id": new_s.id, "session_mode": new_s.session_mode.value, "status": new_s.status.value}


@app.get("/session/by-phone-platform/{user_phone}/{platform}")
async def sessions_by_phone_platform(user_phone: str, platform: str, db: AsyncSession = Depends(get_db_session)):
    res = await db.execute(
        select(models.Session).where(
            models.Session.user_phone == user_phone,
            models.Session.platform == platform,
        )
    )
    rows = res.scalars().all()
    return [{"id": r.id, "bot_id": r.bot_id, "status": r.status.value, "session_mode": r.session_mode.value} for r in rows]


@app.post("/event/create")
async def event_create(payload: CreateEventReq, db: AsyncSession = Depends(get_db_session)):
    # Protect critical updates: try DB-level row lock (SELECT FOR UPDATE) inside a transaction.
    # If the DB doesn't support it or a transaction can't be started, fall back to the
    # optimistic flush/commit path already in use.
    max_attempts = 3
    backoff = 0.05
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
                            select(models.SessionStateCycle).where(models.SessionStateCycle.session_id == session.id, models.SessionStateCycle.completed_at == None)
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
                            await _emit_affiliate_cycle_created(cycle, session)
                            session.state = new_state
                            session.state_entered_at = datetime.utcnow()
                            db.add(session)

                        if new_state == models.SessionState.closed:
                            session.status = models.SessionStatus.closed
                            session.closed_at = datetime.utcnow()
                            try:
                                session.duration_seconds = int((session.closed_at - session.created_at).total_seconds())
                            except Exception:
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
                        actor_id=ev.user_phone,
                        entity_type="event",
                        entity_id=ev.id,
                        metadata={"session_id": ev.session_id, "bot_id": payload.bot_id},
                    )

                    try:
                        await event_publisher.publish_business_event(session.business_id or session.bot_id, {"event_id": ev.id, "session_id": session.id})
                    except Exception:
                        pass

                    return {"event_id": ev.id, "session_id": ev.session_id, "message_count": ev.message_count}
            except (InvalidRequestError, DatabaseError):
                # DB-level locking not supported / transaction couldn't be started; fall back to optimistic commit path
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
                        select(models.SessionStateCycle).where(models.SessionStateCycle.session_id == session.id, models.SessionStateCycle.completed_at == None)
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
                        await _emit_affiliate_cycle_created(cycle, session)
                        session.state = new_state
                        session.state_entered_at = datetime.utcnow()
                        db.add(session)

                    if new_state == models.SessionState.closed:
                        session.status = models.SessionStatus.closed
                        session.closed_at = datetime.utcnow()
                        try:
                            session.duration_seconds = int((session.closed_at - session.created_at).total_seconds())
                        except Exception:
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
                    actor_id=ev.user_phone,
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


@app.put("/event/{event_id}/update")
async def event_update(event_id: str, body: dict, db: AsyncSession = Depends(get_db_session)):
    res = await db.execute(select(models.Event).where(models.Event.id == event_id))
    ev = res.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="event not found")

    upd = body.get("updated_fields")
    if upd:
        ev.updated_fields = {**(ev.updated_fields or {}), **upd}

    if body.get("append_payload_event"):
        payload = ev.payload_events or {}
        events = payload.get("events", [])
        events.append(body["append_payload_event"])
        payload["events"] = events
        ev.payload_events = payload

    if "status" in body and body["status"] is not None:
        ev.status = body["status"]

    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return {"event_id": ev.id, "status": ev.status}


@app.get("/event/{event_id}")
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


@app.get("/event/session/{session_id}")
async def events_for_session(session_id: str, db: AsyncSession = Depends(get_db_session)):
    res = await db.execute(
        select(models.Event)
        .where(models.Event.session_id == session_id)
        .order_by(models.Event.created_at.desc())
    )
    rows = res.scalars().all()
    return [{"id": r.id, "event_type": r.event_type, "created_at": r.created_at, "message_count": r.message_count} for r in rows]


@app.get("/session/{session_id}/cycles")
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

    await db.commit()
    await db.refresh(new_cycle)
    await db.refresh(s)
    await _emit_affiliate_cycle_created(new_cycle, s)

    await audit_client.emit_audit(
        service="bot-session",
        event_type="cycle_upgraded",
        payload={"session_id": session_id, "old_cycle_id": c.id, "new_cycle_id": new_cycle.id, "new_state": new_state.value},
        actor_id=s.user_phone,
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

