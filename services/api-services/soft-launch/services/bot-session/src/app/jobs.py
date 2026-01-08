import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete
from .db import async_engine, AsyncSessionLocal
from .models import Session, Event, SessionStatus

logger = logging.getLogger("bot_session.jobs")


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
