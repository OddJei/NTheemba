from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.config import get_event_source, get_msme_base_url
from src.app.models import OutboxEvent
from libs.outbox.outbox import create_outbox_row


async def add_outbox_event(
    *,
    db: AsyncSession,
    event_type: str,
    business_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    # Insert a canonical outbox row so dispatchers read from `public.outbox`.
    payload = {
        "event_type": event_type,
        "business_id": business_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "source": get_event_source(),
        "meta": meta,
    }
    # Route inventory notifications to the MSME notification proxy
    destination: Optional[str] = None
    if event_type in ("inventory.out_of_stock", "inventory.low_stock"):
        destination = f"{get_msme_base_url().rstrip('/')}/notification/send"

    await create_outbox_row(db, event_type, payload, destination=destination, correlation_id=correlation_id, producer="catalog-inventory")
    return None
