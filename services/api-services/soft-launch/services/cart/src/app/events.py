from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models import OutboxEvent
from src.app.helpers.outbox.outbox import create_outbox_row


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
    # store event in canonical public.outbox for later delivery
    await create_outbox_row(
        db,
        event_type,
        payload,
        destination=None,
        correlation_id=correlation_id,
        producer="cart",
    )
    await db.commit()
