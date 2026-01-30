from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional
import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from src.app.config import (
    get_notification_base_url,
    get_notification_timeout_seconds,
    get_payment_revenue_base_url,
    get_jwt_secret,
    get_access_token_minutes,
    get_subscription_price_minor,
    get_subscription_currency,
)
from src.app.security import jwt_encode
from src.app.models import Business, SubscriptionReminder
from src.app.audit_client import emit_audit_sync

logger = logging.getLogger("subscription_reminder")

# Reminder schedule (days before expiry): 7, 3, 1
REMINDER_DAYS = [7, 3, 1]


@dataclass
class BizSnapshot:
    id: str
    owner_id: Optional[str]
    subscription_expiry: Optional[datetime]
    subscription_plan: Optional[str]
    is_active: bool


@dataclass
class ReminderRecord:
    business_id: str
    reminders_sent: int = 0
    last_reminder_at: Optional[datetime] = None
    auto_pay_attempted: bool = False


def compute_reminder_actions(biz: BizSnapshot, record: ReminderRecord, now: Optional[datetime] = None) -> List[str]:
    """Return actions to take for a single business given its reminder record.

    Actions are strings: 'send_reminder_1', 'send_reminder_2', 'send_reminder_3', 'attempt_auto_pay', 'expire_account'
    This is pure logic for easy unit testing.
    """
    now = now or datetime.now(timezone.utc)
    actions: List[str] = []

    if not biz.is_active or (biz.subscription_plan or "").lower() != "paid":
        return actions

    if not biz.subscription_expiry:
        return actions

    expiry = biz.subscription_expiry
    # send reminders
    for idx, days in enumerate(REMINDER_DAYS):
        target = expiry - timedelta(days=days)
        reminder_number = idx + 1
        if now >= target and record.reminders_sent < reminder_number:
            actions.append(f"send_reminder_{reminder_number}")
            record.reminders_sent = reminder_number

    # If at-or-past expiry, and we haven't yet attempted auto-pay, attempt it
    if now >= expiry:
        if not record.auto_pay_attempted:
            actions.append("attempt_auto_pay")
        else:
            # auto-pay attempted and still expired -> expire account
            actions.append("expire_account")

    return actions


async def background_loop(get_db_session_provider: Callable[[], object], app, interval_seconds: int = 3600) -> None:
    """Background loop that periodically processes subscriptions.

    For robustness in this soft-launch repo the implementation is best-effort and logs errors.
    The real DB interactions are intentionally left thin here so unit tests can focus on pure logic.
    """
    while True:
        try:
            # Acquire a DB session provider and call a hook if available. This is intentionally
            # lightweight here — production would have a full implementation to query and update DB.
            # We attempt to call a optional hook `process_due_subscriptions` if present on the module
            # using the provided provider.
            if hasattr(process_due_subscriptions, "__call__"):
                async for db in get_db_session_provider():
                    try:
                        await process_due_subscriptions(db)
                    except Exception:
                        logger.exception("error_processing_due_subscriptions")
                    break
        except Exception:
            logger.exception("subscription_reminder_loop_error")
        await asyncio.sleep(interval_seconds)


async def process_due_subscriptions(db) -> None:
    """Optional DB-backed runner.

    This minimal implementation queries `Business` rows and creates/updates a small reminder record
    stored in memory via `business.subscription_expiry` and logs actions. It avoids heavy schema
    changes for soft-launch — prefer testing `compute_reminder_actions` in unit tests.
    """
    # Query businesses with paid plan and expiry set
    now = datetime.now(timezone.utc)
    try:
        stmt = select(Business).where(
            Business.subscription_plan == "paid",
        )
        results = (await db.execute(stmt)).scalars().all()
    except Exception:
        logger.exception("failed_querying_businesses")
        return

    notif_base = get_notification_base_url().rstrip("/")
    notif_timeout = get_notification_timeout_seconds()
    pr_base = get_payment_revenue_base_url().rstrip("/")

    async with httpx.AsyncClient(timeout=notif_timeout) as client:
        for b in results:
            try:
                # skip inactive or missing expiry
                if not bool(b.is_active) or not b.subscription_expiry:
                    continue

                # load or create reminder record
                rem = (await db.execute(select(SubscriptionReminder).where(SubscriptionReminder.business_id == b.id))).scalar_one_or_none()
                if not rem:
                    rem = SubscriptionReminder(business_id=b.id)
                    db.add(rem)
                    await db.flush()

                record = ReminderRecord(business_id=rem.business_id, reminders_sent=rem.reminders_sent, last_reminder_at=rem.last_reminder_at, auto_pay_attempted=rem.auto_pay_attempted)
                snapshot = BizSnapshot(id=b.id, owner_id=b.owner_id, subscription_expiry=b.subscription_expiry, subscription_plan=b.subscription_plan, is_active=bool(b.is_active))
                actions = compute_reminder_actions(snapshot, record, now=now)

                for act in actions:
                    if act.startswith("send_reminder"):
                        # send friendly in-app notification with amount and days-left
                        try:
                            days_left = max(0, (b.subscription_expiry - now).days) if b.subscription_expiry else None
                        except Exception:
                            days_left = None

                        amount = getattr(b, "subscription_price_minor", None) or get_subscription_price_minor((b.subscription_plan or "").lower())
                        currency = getattr(b, "subscription_currency", None) or get_subscription_currency((b.subscription_plan or "").lower())

                        if act == "send_reminder_1":
                            human_msg = f"Your paid subscription will expire in {days_left or 7} days. We'll attempt auto-payment at expiry."
                        elif act == "send_reminder_2":
                            human_msg = f"Reminder: your subscription expires in {days_left or 3} days. Please ensure payment details are up to date."
                        else:
                            human_msg = f"Final reminder: your subscription expires in {days_left or 1} day. We'll attempt auto-payment now if enabled."

                        template = "subscription_reminder"
                        payload = {
                            "reminder": act,
                            "days_left": days_left,
                            "amount_minor": int(amount or 0),
                            "currency": currency,
                            "message": human_msg,
                        }
                        headers = {}
                        try:
                            await client.post(f"{notif_base}/notification/send", json={"channel": "in_app", "user_id": b.owner_id, "business_id": b.id, "template": template, "payload": payload}, headers=headers)
                        except Exception:
                            logger.exception("notify_failed")
                        rem.reminders_sent = record.reminders_sent
                        rem.last_reminder_at = datetime.now(timezone.utc)
                        await db.commit()
                        # Emit audit: reminder sent
                        try:
                            emit_audit_sync(
                                service="msme-engine",
                                event_type="subscription_reminder_sent",
                                payload={"reminder": act, "days_left": days_left, "amount_minor": int(amount or 0), "currency": currency},
                                actor_id=b.owner_id,
                                entity_type="business",
                                entity_id=b.id,
                                severity="info",
                                metadata={"correlation_id": getattr(b, 'correlation_id', None)},
                            )
                        except Exception:
                            logger.exception("audit_emit_failed_reminder_sent")

                    if act == "attempt_auto_pay":
                            if act == "attempt_auto_pay":
                                # attempt payment via payment-revenue; include actual plan amount
                                now_ts = datetime.now(timezone.utc)
                                exp_ts = now_ts + timedelta(minutes=get_access_token_minutes())
                                token = jwt_encode({"sub": "msme-scheduler", "role": "staff", "iat": int(now_ts.timestamp()), "exp": int(exp_ts.timestamp()), "typ": "access"}, secret=get_jwt_secret())
                                headers = {"Authorization": f"Bearer {token}"}

                                # determine amount and currency: prefer business-stored price, else config defaults
                                amount_minor = getattr(b, "subscription_price_minor", None) or get_subscription_price_minor((b.subscription_plan or "").lower())
                                currency = getattr(b, "subscription_currency", None) or get_subscription_currency((b.subscription_plan or "").lower())

                                body = {
                                    "depositId": None,
                                    "order_id": None,
                                    "business_id": b.id,
                                    "amount_minor": int(amount_minor or 0),
                                    "currency": currency or "ZMW",
                                    "phoneNumber": None,
                                    "provider": None,
                                    "metadata": {"reference": "auto_pay", "source": "msme-scheduler"},
                                }

                                try:
                                    await client.post(f"{pr_base}/pawapay/deposits/initiate", json=body, headers=headers)
                                except Exception:
                                    logger.exception("auto_pay_request_failed")
                                rem.auto_pay_attempted = True
                                await db.commit()
                                # Emit audit: auto-pay attempted
                                try:
                                    emit_audit_sync(
                                        service="msme-engine",
                                        event_type="subscription_auto_pay_attempt",
                                        payload={"amount_minor": int(amount_minor or 0), "currency": currency},
                                        actor_id="msme-scheduler",
                                        entity_type="business",
                                        entity_id=b.id,
                                        severity="info",
                                        metadata={"correlation_id": None},
                                    )
                                except Exception:
                                    logger.exception("audit_emit_failed_auto_pay_attempt")

                    if act == "expire_account":
                        # Downgrade business to free plan and persist fields; keep owner role unchanged.
                        try:
                            b.subscription_plan = "free"
                            b.subscription_expiry = None
                            b.subscription_price_minor = 0
                            b.subscription_currency = get_subscription_currency("free")
                            b.is_active = True
                            await db.flush()

                            # notify owner about downgrade (best-effort)
                            try:
                                payload = {"plan": "free", "message": "Your subscription was downgraded to the free plan after a failed auto-pay attempt."}
                                await client.post(f"{notif_base}/notification/send", json={"channel": "in_app", "user_id": b.owner_id, "business_id": b.id, "template": "subscription_downgraded", "payload": payload})
                            except Exception:
                                logger.exception("notify_downgrade_failed")
                        except Exception:
                            logger.exception("expire_account_failed")
                        await db.commit()
                        # Emit audit: subscription downgraded
                        try:
                            emit_audit_sync(
                                service="msme-engine",
                                event_type="subscription_downgraded",
                                payload={"new_plan": "free"},
                                actor_id="msme-scheduler",
                                entity_type="business",
                                entity_id=b.id,
                                severity="warning",
                                metadata={"correlation_id": None},
                            )
                        except Exception:
                            logger.exception("audit_emit_failed_downgrade")
            except Exception:
                logger.exception("processing_business_failed")
