from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.config import get_event_source
from src.app.models import OutboxEvent


def add_outbox_event(
    *,
    db: AsyncSession,
    event_type: str,
    business_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> OutboxEvent:
    evt = OutboxEvent(
        event_type=event_type,
        business_id=business_id,
        entity_type=entity_type,
        entity_id=entity_id,
        source=get_event_source(),
        correlation_id=correlation_id,
        meta=meta,
    )
    db.add(evt)
    return evt
