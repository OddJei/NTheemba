from __future__ import annotations

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.config import get_notification_base_url


async def emit_notification_outbox(
    db: AsyncSession,
    *,
    channel: str,
    user_id: str | None = None,
    business_id: str | None = None,
    payload: dict | None = None,
    dedupe_key: str | None = None,
) -> str:
    """Create an OutboxEvent row targeting the Notification service.

    Channel should be 'whatsapp' or 'email'. Returns the outbox id.
    """
    from app.helpers.outbox.outbox import create_outbox_row
    from src.app.config import get_pg_schema

    base = (get_notification_base_url() or "http://notification:8570").rstrip("/")
    target = f"{base}/notification/send"

    event_type = f"notification.{channel}"
    out_id = str(uuid.uuid4())

    schema = get_pg_schema()
    table = f"{schema}.outbox_events"
    await create_outbox_row(
        db,
        event_type,
        {
            "user_id": user_id,
            "business_id": business_id,
            "channel": channel,
            "payload": payload or {},
        },
        id=out_id,
        destination=target,
        table=table,
    )

    await db.commit()
    return out_id
