from __future__ import annotations

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.config import get_notification_base_url
from libs.outbox.outbox import create_outbox_row


async def emit_notification_outbox(
    db: AsyncSession,
    *,
    channel: str,
    user_id: str | None = None,
    business_id: str | None = None,
    payload: dict | None = None,
    dedupe_key: str | None = None,
) -> str:
    """Create an Outbox row targeting the Notification service.

    Channel should be 'whatsapp' or 'email'. Returns the outbox id.
    """
    base = (get_notification_base_url() or "http://notification:8570").rstrip("/")
    destination = f"{base}/notification/send"

    topic = f"notification.{channel}"
    out_id = str(uuid.uuid4())

    await create_outbox_row(
        db,
        topic,
        {
            "user_id": user_id,
            "business_id": business_id,
            "channel": channel,
            "payload": payload or {},
        },
        id=out_id,
        destination=destination,
        idempotency_key=dedupe_key,
        producer="affiliate-engine",
    )
    await db.commit()
    return out_id
