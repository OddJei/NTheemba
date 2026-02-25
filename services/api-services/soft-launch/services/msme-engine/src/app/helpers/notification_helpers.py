from __future__ import annotations

import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.config import get_notification_base_url

from src.app.helpers.outbox.outbox import emit_notification

logger = logging.getLogger("msme_engine.notification")


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
    base = (get_notification_base_url() or "http://notification:8570").rstrip("/")
    target = f"{base}/notification/send"

    logger.info("notification_outbox_prepare", extra={"topic": f"notification.{channel}", "destination": target})

    out_id = await emit_notification(
        db,
        channel,
        user_id=user_id,
        business_id=business_id,
        payload={"destination": target, **(payload or {})},
        dedupe_key=dedupe_key,
        producer="notification-emitter",
    )

    logger.info("notification_outbox_written", extra={"out_id": str(out_id)})
    return str(out_id)
