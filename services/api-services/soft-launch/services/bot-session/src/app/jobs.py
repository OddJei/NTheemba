import asyncio
import logging
from datetime import datetime, timedelta
import os
import httpx
from sqlalchemy import select, update, delete
from .db import async_engine, AsyncSessionLocal
from .models import Session, Event, SessionStatus, SessionStateCycle, SessionState
from . import audit_client

logger = logging.getLogger("bot_session.jobs")


def _get_notification_base_url() -> str:
    return os.getenv("NOTIFICATION_BASE_URL", "http://127.0.0.1:8570")


def _get_notification_timeout_seconds() -> float:
    try:
        return float(os.getenv("NOTIFICATION_TIMEOUT_SECONDS", "3.0"))
    except ValueError:
        return 3.0


async def _notify_admin(*, business_id: str | None, template: str, payload: dict, correlation_id: str | None) -> None:
    base = _get_notification_base_url().rstrip("/")
    timeout = _get_notification_timeout_seconds()
    headers: dict[str, str] = {}
    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            await client.post(
                f"{base}/notification/send",
                json={
                    "channel": "in_app",
                    "user_id": None,
                    "business_id": business_id,
                    "template": template,
                    "payload": payload,
                },
                headers=headers,
            )
    except httpx.RequestError:
        logger.info("notification_unreachable", extra={"template": template, "correlation_id": correlation_id})


async def _cleanup_task(inactivity_days: int = 30, retention_days: int = 90, run_once: bool = False):
    """Mark sessions inactive if not updated within inactivity_days and delete old events older than retention_days."""
    async with AsyncSessionLocal() as db:
        try:
            # mark sessions inactive
            cutoff = datetime.utcnow() - timedelta(days=inactivity_days)
            stmt = update(Session).where(Session.status == SessionStatus.active, Session.updated_at < cutoff).values(status=SessionStatus.inactive)
            await db.execute(stmt)

            # delete events older than retention
            ev_cutoff = datetime.utcnow() - timedelta(days=retention_days)
            del_stmt = delete(Event).where(Event.created_at < ev_cutoff)
            await db.execute(del_stmt)

            await db.commit()
            logger.info("cleanup completed: sessions older than %s marked inactive; events older than %s deleted", inactivity_days, retention_days)
        except Exception:
            logger.exception("cleanup task failed")

    if not run_once:
        while True:
            await asyncio.sleep(60 * 60)  # run hourly
            await _cleanup_task(inactivity_days=inactivity_days, retention_days=retention_days, run_once=True)


def schedule_cleanup(app):
    loop = asyncio.get_event_loop()
    loop.create_task(_cleanup_task())


async def _sweep_abandoned_sessions(*, session_hours: int = 24, cycle_hours: int = 8, notify_lag_hours: int = 2, run_once: bool = False):
    session_cutoff = datetime.utcnow() - timedelta(hours=session_hours)
    cycle_cutoff = datetime.utcnow() - timedelta(hours=cycle_hours)
    notify_cutoff = datetime.utcnow() - timedelta(hours=notify_lag_hours)

    async with AsyncSessionLocal() as db:
        try:
            # Mark inactive sessions (user-bot sessions after 24h)
            sess_stmt = (
                update(Session)
                .where(Session.status == SessionStatus.active, Session.updated_at < session_cutoff)
                .values(status=SessionStatus.inactive)
            )
            await db.execute(sess_stmt)

            # Sweep abandoned cycles
            res_cycles = await db.execute(
                select(SessionStateCycle, Session)
                .join(Session, Session.id == SessionStateCycle.session_id)
                .where(SessionStateCycle.completed_at == None, SessionStateCycle.started_at < cycle_cutoff)
            )
            rows = res_cycles.all()
            for cycle, session in rows:
                if cycle.cycle_state == SessionState.delivery:
                    payload = {
                        "session_id": session.id,
                        "cycle_id": cycle.id,
                        "cycle_state": cycle.cycle_state.value,
                        "started_at": cycle.started_at,
                    }
                    await audit_client.emit_audit(
                        service="bot-session",
                        event_type="delivery_cycle_stuck",
                        payload=payload,
                        actor_id=session.user_phone,
                        entity_type="session",
                        entity_id=session.id,
                        metadata={"business_id": session.business_id},
                    )
                    await _notify_admin(
                        business_id=session.business_id,
                        template="delivery_cycle_stuck",
                        payload=payload,
                        correlation_id=str(cycle.id),
                    )
                else:
                    cycle.completed_at = datetime.utcnow()
                    db.add(cycle)

            # Notify admin on stuck order/payment cycles
            res_open = await db.execute(
                select(SessionStateCycle, Session)
                .join(Session, Session.id == SessionStateCycle.session_id)
                .where(SessionStateCycle.completed_at == None, SessionStateCycle.started_at < notify_cutoff)
            )
            rows_open = res_open.all()
            for cycle, session in rows_open:
                ctx = (cycle.meta or {}).get("context") if isinstance(cycle.meta, dict) else None
                ctx = ctx if isinstance(ctx, dict) else {}
                if cycle.cycle_state == SessionState.order and ctx.get("confirmed_order") is True:
                    payload = {
                        "session_id": session.id,
                        "cycle_id": cycle.id,
                        "cycle_state": "order",
                        "order_id": ctx.get("order_id"),
                    }
                    await audit_client.emit_audit(
                        service="bot-session",
                        event_type="order_stuck_before_payment",
                        payload=payload,
                        actor_id=session.user_phone,
                        entity_type="session",
                        entity_id=session.id,
                        metadata={"business_id": session.business_id},
                    )
                    await _notify_admin(
                        business_id=session.business_id,
                        template="order_stuck_before_payment",
                        payload=payload,
                        correlation_id=str(cycle.id),
                    )
                if cycle.cycle_state == SessionState.payment and ctx.get("confirm_payment") is True:
                    payload = {
                        "session_id": session.id,
                        "cycle_id": cycle.id,
                        "cycle_state": "payment",
                        "payment_id": ctx.get("payment_id"),
                    }
                    await audit_client.emit_audit(
                        service="bot-session",
                        event_type="payment_stuck_before_delivery",
                        payload=payload,
                        actor_id=session.user_phone,
                        entity_type="session",
                        entity_id=session.id,
                        metadata={"business_id": session.business_id},
                    )
                    await _notify_admin(
                        business_id=session.business_id,
                        template="payment_stuck_before_delivery",
                        payload=payload,
                        correlation_id=str(cycle.id),
                    )

            await db.commit()
            logger.info("sweep completed: inactive sessions and stale cycles processed")
        except Exception:
            await db.rollback()
            logger.exception("sweep task failed")

    if not run_once:
        while True:
            await asyncio.sleep(60 * 60)
            await _sweep_abandoned_sessions(session_hours=session_hours, cycle_hours=cycle_hours, notify_lag_hours=notify_lag_hours, run_once=True)


def schedule_sweeps(app):
    loop = asyncio.get_event_loop()
    loop.create_task(_sweep_abandoned_sessions())
