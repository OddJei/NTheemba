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
    affiliate_code: Optional[str] = None
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
        if payload.affiliate_code or payload.affiliate_id or payload.affiliate_metadata:
            # Initial SessionStateCycle: captures affiliate attribution at session creation.
            # This is recorded separately from the Session row so attribution is tracked per cycle.
            cycle = models.SessionStateCycle(
                session_id=session_obj.id,
                cycle_type=session_obj.state,
                started_at=datetime.utcnow(),
                initiated_by_affiliate=True,
                affiliate_code=payload.affiliate_code,
                affiliate_id=payload.affiliate_id,
                meta=payload.affiliate_metadata,
            )
            db.add(cycle)
            await db.commit()

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
            "cycle_type": c.cycle_type.value,
            "started_at": c.started_at,
            "completed_at": c.completed_at,
            "initiated_by_affiliate": c.initiated_by_affiliate,
            "affiliate_code": c.affiliate_code,
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

    return {"session_id": s.id, "status": s.status.value, "closed_at": s.closed_at}


@app.get("/session/resolve")
async def resolve_session(
    user_phone: Optional[str] = None,
    bot_id: Optional[str] = None,
    platform: Optional[str] = None,
    affiliate_code: Optional[str] = None,
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
    if affiliate_code or affiliate_id or affiliate_metadata:
        # Initial SessionStateCycle on session resolution when affiliate attribution
        # is provided by the resolver call.
        cycle = models.SessionStateCycle(
            session_id=new_s.id,
            cycle_type=new_s.state,
            started_at=datetime.utcnow(),
            initiated_by_affiliate=True,
            affiliate_code=affiliate_code,
            affiliate_id=affiliate_id,
            meta=affiliate_metadata,
        )
        db.add(cycle)
        await db.commit()
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
                            aff_code = open_cycle.affiliate_code
                            aff_id = open_cycle.affiliate_id
                            aff_meta = open_cycle.meta
                            open_cycle.completed_at = datetime.utcnow()
                            db.add(open_cycle)
                            return {"affiliate_code": aff_code, "affiliate_id": aff_id, "affiliate_metadata": aff_meta}
                        return {"affiliate_code": None, "affiliate_id": None, "affiliate_metadata": None}

                    et = (payload.event_type or "")
                    if et in transition_map:
                        new_state = transition_map[et]
                        if session.state != new_state:
                            # On state transition: complete any open cycle and create
                            # a new SessionStateCycle for the `new_state`.
                            prior_aff = await _fetch_and_complete_open_cycle()
                            cycle = models.SessionStateCycle(
                                session_id=session.id,
                                cycle_type=new_state,
                                started_at=datetime.utcnow(),
                                initiated_by_affiliate=bool(prior_aff.get("affiliate_code") or prior_aff.get("affiliate_id")),
                                affiliate_code=prior_aff.get("affiliate_code"),
                                affiliate_id=prior_aff.get("affiliate_id"),
                                meta=prior_aff.get("affiliate_metadata"),
                            )
                            db.add(cycle)
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
                        aff_code = open_cycle.affiliate_code
                        aff_id = open_cycle.affiliate_id
                        aff_meta = open_cycle.meta
                        open_cycle.completed_at = datetime.utcnow()
                        db.add(open_cycle)
                        return {"affiliate_code": aff_code, "affiliate_id": aff_id, "affiliate_metadata": aff_meta}
                    return {"affiliate_code": None, "affiliate_id": None, "affiliate_metadata": None}

                et = (payload.event_type or "")
                if et in transition_map:
                    new_state = transition_map[et]
                    if session.state != new_state:
                        prior_aff = await _fetch_and_complete_open_cycle()
                        cycle = models.SessionStateCycle(
                            session_id=session.id,
                            cycle_type=new_state,
                            started_at=datetime.utcnow(),
                            initiated_by_affiliate=bool(prior_aff.get("affiliate_code") or prior_aff.get("affiliate_id")),
                            affiliate_code=prior_aff.get("affiliate_code"),
                            affiliate_id=prior_aff.get("affiliate_id"),
                            meta=prior_aff.get("affiliate_metadata"),
                        )
                        db.add(cycle)
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
            "cycle_type": r.cycle_type.value,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
            "initiated_by_affiliate": r.initiated_by_affiliate,
            "affiliate_code": r.affiliate_code,
            "affiliate_id": r.affiliate_id,
            "meta": r.meta,
        }
        for r in rows
    ]


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

