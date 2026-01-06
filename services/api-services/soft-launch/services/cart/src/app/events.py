from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models import OutboxEvent


async def add_outbox_event(
    db: AsyncSession,
    *,
    event_type: str,
    payload: Any,
    business_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    correlation_id: str | None = None,
) -> None:
    # store event for later delivery (outbox pattern)
    ev = OutboxEvent(
        event_type=event_type,
        business_id=business_id,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        correlation_id=correlation_id,
    )
    db.add(ev)
    await db.commit()
