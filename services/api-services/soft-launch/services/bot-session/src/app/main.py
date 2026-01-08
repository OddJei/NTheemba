import os
from datetime import datetime
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import events as event_publisher
from . import jobs
from . import models
from .db import Base, async_engine, get_db_session


app = FastAPI(title="Bot-Session Unified Service")


class CreateSessionReq(BaseModel):
    user_phone: str
    bot_id: Optional[str] = None
    bot_phone: Optional[str] = None
    bot_type: Optional[str] = None
    business_id: Optional[str] = None
    platform: str


class CreateEventReq(BaseModel):
    session_id: str
    user_phone: Optional[str] = None
    bot_id: str
    payload_events: Optional[dict] = None
    last_event_id: Optional[str] = None
    event_type: Optional[str] = None


@app.on_event("startup")
async def startup() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    if os.getenv("DISABLE_CLEANUP_JOBS") != "1":
        try:
            jobs.schedule_cleanup(app)
        except Exception:
            pass


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
        existing.status = models.SessionStatus.active
        existing.session_mode = session_mode
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
        )
        db.add(session_obj)
        await db.commit()
        await db.refresh(session_obj)
        reactivated = False

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


@app.get("/session/resolve")
async def resolve_session(
    user_phone: Optional[str] = None,
    bot_id: Optional[str] = None,
    platform: Optional[str] = None,
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
    )
    db.add(new_s)
    await db.commit()
    await db.refresh(new_s)
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
    res_s = await db.execute(select(models.Session).where(models.Session.id == payload.session_id))
    session = res_s.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

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
    await db.commit()
    await db.refresh(ev)

    session.last_event_id = ev.id
    db.add(session)
    await db.commit()

    try:
        await event_publisher.publish_business_event(session.business_id or session.bot_id, {"event_id": ev.id, "session_id": session.id})
    except Exception:
        pass

    return {"event_id": ev.id, "session_id": ev.session_id, "message_count": ev.message_count}


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

