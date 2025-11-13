import asyncio
from datetime import datetime
from app.models.db import AsyncSessionLocal
from app.models.notifications import Notification
from app.models.schemas import NotificationCreate
from app.utils.gateways.sms import send_sms
from app.utils.gateways.email import send_email
from typing import Tuple
from app.utils.audit import log_event
from sqlalchemy import select
from app.config.settings import settings
import os


class NotificationService:
    """Simple service to persist notifications and call gateway stubs.

    This is intentionally minimal: persists a Notification record then attempts to send
    synchronously using stubbed gateways. Failures are recorded on the model.
    """

    def __init__(self):
        self.db = None

    async def create_and_send(self, payload: NotificationCreate, metadata: dict | None = None):
        # create notification record
        async with AsyncSessionLocal() as session:
            async with session.begin():
                n = Notification(
                    user_id=payload.user_id,
                    business_id=payload.business_id,
                    channel=payload.channel,
                    template=payload.template,
                    payload=payload.payload,
                    status="pending",
                )
                session.add(n)
            await session.refresh(n)

        # Determine notifier toggle: prefer explicit process env so tests can
        # flip behavior at runtime (pytest sets env before importing).
        env_val = os.getenv("NOTIFIER_ENABLED")
        notifier_enabled = None
        if env_val is not None:
            notifier_enabled = env_val.lower() in ("1", "true", "yes")
        else:
            notifier_enabled = getattr(settings, "NOTIFIER_ENABLED", True)

        # If notifier is disabled at runtime, skip outbound calls and log.
        if not notifier_enabled:
            # update record to indicate notifier was disabled
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    db_n = await session.get(Notification, n.id)
                    db_n.status = "notifier_disabled"
                    db_n.error_message = None
                    session.add(db_n)
                await session.refresh(db_n)

            # Log to console the notification payload and whether audit is enabled
            try:
                import logging, json

                logger = logging.getLogger("notification.notifier")
                # Determine audit_enabled the same way other modules do: prefer
                # the process env override so runtime flags and tests behave
                # consistently.
                env_audit = os.getenv("AUDIT_ENABLED")
                if env_audit is not None:
                    audit_enabled_value = env_audit.lower() in ("1", "true", "yes")
                else:
                    audit_enabled_value = getattr(settings, "AUDIT_ENABLED", True)

                logger.info("NOTIFIER_DISABLED: %s", json.dumps({
                    "notification_id": n.id,
                    "user_id": n.user_id,
                    "channel": n.channel,
                    "template": n.template,
                    "payload": n.payload,
                    "AUDIT_ENABLED": audit_enabled_value,
                }))
            except Exception:
                import logging

                logging.getLogger("notification.notifier").info("NOTIFIER_DISABLED: (could not serialize notification)")

            # If audit is enabled, still emit an audit event; otherwise do not
            # call the audit service but ensure the console log already indicated that.
            if getattr(settings, "AUDIT_ENABLED", True):
                asyncio.create_task(
                    log_event(
                        service="notification-service",
                        event_type="notification_skipped_notifier",
                        actor_id=(n.user_id or "system"),
                        entity_type="notification",
                        entity_id=n.id,
                        payload={"channel": n.channel, "status": "notifier_disabled"},
                        metadata=(metadata or {}),
                    )
                )

            return db_n

        # Try to send based on channel using async gateways
        try:
            # n here is an ORM instance with attribute values; use the
            # attribute strings for branching
            ch = getattr(n, "channel", None)
            if ch == "sms":
                ok, err = await send_sms(n)
            elif ch == "email":
                ok, err = await send_email(n)
            else:
                ok, err = False, "unsupported channel"

            # update record
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    db_n = await session.get(Notification, n.id)
                    if ok:
                        db_n.status = "sent"
                        db_n.sent_at = datetime.utcnow()
                        db_n.error_message = None
                    else:
                        db_n.status = "failed"
                        db_n.error_message = err or "unknown error"
                    session.add(db_n)
                await session.refresh(db_n)
                # Log audit event asynchronously (don't wait for it)
                asyncio.create_task(
                    log_event(
                        service="notification-service",
                        event_type=("notification_sent" if ok else "notification_failed"),
                        actor_id=(db_n.user_id or "system"),
                        entity_type="notification",
                        entity_id=db_n.id,
                        payload={"channel": db_n.channel, "status": db_n.status},
                        metadata=(metadata or {}),
                    )
                )
                return db_n

        except Exception as exc:  # pragma: no cover - minimal scaffold
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    db_n = await session.get(Notification, n.id)
                    db_n.status = "failed"
                    db_n.error_message = str(exc)
                    session.add(db_n)
                await session.refresh(db_n)
                # audit failure
                asyncio.create_task(
                    log_event(
                        service="notification-service",
                        event_type="notification_failed",
                        actor_id=(db_n.user_id or "system"),
                        entity_type="notification",
                        entity_id=db_n.id,
                        payload={"error": db_n.error_message},
                        metadata=(metadata or {}),
                    )
                )
                return db_n
