from __future__ import annotations

import json
import os
import inspect
from collections.abc import Awaitable
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, Table, MetaData, Column, String, DateTime, JSON as SQLJSON, insert as sa_insert, func
from sqlalchemy.exc import PendingRollbackError
import re

from prometheus_client import Counter
import importlib

try:
    sentry_sdk = importlib.import_module("sentry_sdk")
except Exception:
    sentry_sdk = None

from src.app.models import OutboxEvent
from src.app.config import get_notification_base_url, get_payment_revenue_base_url
import logging

logger = logging.getLogger("msme_engine.outbox")

# Metrics
OUTBOX_FAILURES = Counter("msme_outbox_failures_total", "Total outbox create failures", ["topic", "producer"])
OUTBOX_HIGH_RETRIES = Counter("msme_outbox_high_retries_total", "Outbox events with high retry counts", ["topic", "producer"])


async def create_outbox_row(
    db: AsyncSession,
    topic_or_event_type: Optional[str] = None,
    payload: dict | None = None,
    topic: Optional[str] = None,
    *,
    id: Optional[str] = None,
    destination: Optional[str] = None,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    dedupe_key: Optional[str] = None,
    send_after: Optional[datetime] = None,
    producer: Optional[str] = None,
    headers: Optional[dict] = None,
    table: Optional[str] = None,
    commit: bool = False,
) -> str | uuid.UUID:
    """Insert an outbox row into `msme_engine.outbox_events` and return its id.

    Commits by default; set `commit=False` to include this write in a larger
    transaction.
    """
    # Resolve topic: accept `topic` keyword for new callers or
    # `topic_or_event_type` for legacy callers, then validate.
    event_topic = topic or topic_or_event_type
    # Validate inputs early
    if event_topic is None:
        raise ValueError("event topic required")
    now = datetime.utcnow()
    # accept both `dedupe_key` and legacy `idempotency_key`
    if dedupe_key and not idempotency_key:
        idempotency_key = dedupe_key
    if payload is None:
        payload = {}

    if table:
        # Ensure id is present
        if not id:
            id = str(uuid.uuid4())

        # Parse optional schema-qualified table name `schema.table` or `table`
        if not isinstance(table, str) or not table:
            raise ValueError("invalid table name")

        if "." in table:
            schema_name, tbl_name = table.split(".", 1)
        else:
            schema_name, tbl_name = None, table

        def _valid_ident(n: str) -> bool:
            return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n))

        if schema_name and not _valid_ident(schema_name):
            raise ValueError("invalid schema name")
        if not _valid_ident(tbl_name):
            raise ValueError("invalid table name")

        payload_json = json.dumps(payload)
        headers_json = json.dumps(headers or {})

        # Build a parameterized insert via SQLAlchemy core but with validated identifiers
        qualified = f'"{schema_name}"."{tbl_name}"' if schema_name else f'"{tbl_name}"'
        cols = "id, topic, destination, payload, headers, producer, correlation_id, dedupe_key, status, attempts, last_error, scheduled_at, priority, created_at, updated_at"
        vals = ":id, :topic, :destination, :payload, :headers, :producer, :correlation_id, :dedupe_key, :status, :attempts, :last_error, :scheduled_at, :priority, :created_at, :updated_at"
        insert_sql = text(f"INSERT INTO {qualified} ({cols}) VALUES ({vals})")

        params = {
            "id": id,
            "topic": event_topic,
            "destination": destination,
            "payload": payload_json,
            "headers": headers_json,
            "producer": producer,
            "correlation_id": correlation_id,
            "dedupe_key": idempotency_key,
            "status": "pending",
            "attempts": 0,
            "last_error": None,
            "scheduled_at": send_after,
            "priority": 0,
            "created_at": now,
            "updated_at": now,
        }

        try:
            res = db.execute(insert_sql, params)
            if inspect.isawaitable(res) or isinstance(res, Awaitable):
                await res
        except PendingRollbackError:
            # session is in a rollback state from a prior failed flush; recover and retry
            try:
                await db.rollback()
            except Exception:
                pass
            res = db.execute(insert_sql, params)
            if inspect.isawaitable(res) or isinstance(res, Awaitable):
                await res
        except Exception as e:
            # Metric + Sentry capture for visibility
            try:
                OUTBOX_FAILURES.labels(topic=event_topic or "unknown", producer=producer or "unknown").inc()
            except Exception:
                pass
            if sentry_sdk is not None:
                sentry_sdk.capture_exception(e)
            raise

        if commit:
            try:
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        return id

    # Otherwise, insert via ORM into msme_engine.outbox_events
    row = OutboxEvent(
        topic=event_topic,
        payload=payload,
        destination=destination,
        headers=headers,
        producer=producer,
        correlation_id=correlation_id,
        dedupe_key=idempotency_key,
    )
    db.add(row)
    try:
        await db.flush()
    except Exception as e:
        try:
            OUTBOX_FAILURES.labels(topic=event_topic or "unknown", producer=producer or "unknown").inc()
        except Exception:
            pass
        if sentry_sdk is not None:
            sentry_sdk.capture_exception(e)
        raise
    out_id = getattr(row, "id")
    if commit:
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return out_id


async def emit_notification(
    db: AsyncSession,
    channel: str,
    *,
    user_id: Optional[str] = None,
    business_id: Optional[str] = None,
    payload: Optional[dict] = None,
    dedupe_key: Optional[str] = None,
    producer: Optional[str] = "msme-engine",
    correlation_id: Optional[str] = None,
    destination: Optional[str] = None,
    commit: bool = True,
) -> uuid.UUID:
    """
    Create an outbox row to send a notification to the configured notification service.

    The notification body will contain the provided user_id, business_id, and payload.

    The notification will be sent to the configured notification service endpoint
    unless an explicit destination is provided.

    :param db: a database session
    :param channel: the notification channel to send to (e.g. 'sms', 'email')
    :param user_id: the user to send the notification to (optional)
    :param business_id: the business to send the notification to (optional)
    :param payload: the notification payload (optional)
    :param dedupe_key: a deduplication key to prevent duplicate notifications (optional)
    :param producer: the producer of the notification (optional)
    :param correlation_id: the correlation ID of the notification (optional)
    :param destination: the explicit notification service endpoint to send to (optional)
    :param commit: whether to commit the write to the outbox row (default: True)
    :return: the ID of the created outbox row
    """
    topic = f"notification.{channel}"
    body = {"user_id": user_id, "business_id": business_id, "body": payload or {}}
    # Resolve destination: prefer explicit, otherwise use configured notification service endpoint
    if not destination:
        base = (get_notification_base_url() or "http://notification:8570").rstrip("/")
        destination = f"{base}/notification/send"

    result = await create_outbox_row(
        db,
        topic=topic,
        payload=body,
        destination=destination,
        producer=producer,
        correlation_id=correlation_id,
        dedupe_key=dedupe_key,
        commit=commit,
    )
    return result if isinstance(result, uuid.UUID) else uuid.UUID(result)


async def emit_msme_referral(
    db: AsyncSession,
    *,
    deposit_id: str,
    affiliate_id: str,
    business_id: str,
    amount_zmw: Optional[float] = None,
    occurred_at: Optional[datetime] = None,
    meta: Optional[dict] = None,
    dedupe_key: Optional[str] = None,
    producer: Optional[str] = "msme-engine",
    correlation_id: Optional[str] = None,
    commit: bool = True,
) -> uuid.UUID:
    """
    Emit a msme.referral event to the affiliate-engine.

    The event will be dispatched to the configured affiliate-engine service endpoint.

    :param db: The database session to use for creating the outbox event.
    :param deposit_id: The deposit ID associated with the referral.
    :param affiliate_id: The affiliate ID associated with the referral.
    :param business_id: The business ID associated with the referral.
    :param amount_zmw: The amount of the referral in ZMW, if applicable.
    :param occurred_at: The datetime at which the referral occurred, if applicable.
    :param meta: Additional metadata associated with the referral, if applicable.
    :param dedupe_key: An optional key to dedupe duplicate events. If not provided, a UUID will be generated.
    :param producer: The producer of the event.
    :param correlation_id: The correlation ID of the event.
    :param commit: If True, commit the outbox event to the database. Otherwise, the operation will be rolled back.
    :return: The UUID of the created outbox event.
    """
    # Instrumentation: log raw values for easier debugging
    logger.info("emit_msme_referral called", extra={"deposit_id": deposit_id, "affiliate_id_raw": affiliate_id, "business_id": business_id, "correlation_id": correlation_id})

    # Validate required identifiers with clearer logging
    try:
        if not deposit_id or not isinstance(deposit_id, str):
            raise ValueError("deposit_id is required and must be a string")
        if not affiliate_id or not isinstance(affiliate_id, str):
            raise ValueError("affiliate_id is required and must be a string")
        if not business_id or not isinstance(business_id, str):
            raise ValueError("business_id is required and must be a string")
    except ValueError as e:
        logger.error("VALIDATION FAILED in emit_msme_referral: %s | deposit_id=%r affiliate_id=%r business_id=%r meta_keys=%s", e, deposit_id, affiliate_id, business_id, (list(meta.keys()) if isinstance(meta, dict) else None))
        raise

    topic = "msme.referral"
    payload = {
        "deposit_id": deposit_id,
        "affiliate_id": affiliate_id,
        "business_id": business_id,
        "amount_zmw": amount_zmw,
        "occurred_at": (occurred_at or datetime.now(timezone.utc)).isoformat(),
        "meta": meta or {},
    }
    # Determine affiliate-engine destination
    referral_base = os.getenv("AFFILIATE_ENGINE_BASE_URL", "http://127.0.0.1:8510").rstrip("/")
    destination = f"{referral_base}/events/msme/referral"

    result = await create_outbox_row(
        db,
        topic=topic,
        payload=payload,
        destination=destination,
        producer=producer,
        correlation_id=correlation_id,
        dedupe_key=dedupe_key,
        commit=commit,
    )
    return result if isinstance(result, uuid.UUID) else uuid.UUID(result)


async def emit_payment_deposit(
    db: AsyncSession,
    *,
    deposit_id: str,
    business_id: str,
    amount_minor: int,
    currency: str,
    status: str,
    provider: Optional[str] = None,
    provider_transaction_id: Optional[str] = None,
    meta: Optional[dict] = None,
    dedupe_key: Optional[str] = None,
    producer: Optional[str] = "msme-engine",
    payment_type: Optional[str] = None,
    correlation_id: Optional[str] = None,
    commit: bool = True,
) -> uuid.UUID:
    # Default topic for deposit callbacks. May be changed for subscription-initiated flows.
    topic = "pawapay.deposit.callback"
    payload = {
        "deposit_id": deposit_id,
        "business_id": business_id,
        "amount_minor": int(amount_minor),
        "currency": str(currency).upper(),
        "status": status,
        "provider": provider,
        "provider_transaction_id": provider_transaction_id,
        "meta": meta or {},
    }
    # If caller indicates this deposit should be initiated by payment-revenue (e.g. subscription),
    # set destination to payment-revenue's initiate endpoint and adjust topic.
    destination = None
    if payment_type and str(payment_type).lower().startswith("sub"):
        topic = "subscription.payment"
        base = (get_payment_revenue_base_url() or "http://payment-revenue:8590").rstrip("/")
        destination = f"{base}/pawapay/deposits/initiate"
        # include declared payment_type in payload
        payload["payment_type"] = "subscription"

    result = await create_outbox_row(
        db,
        topic=topic,
        payload=payload,
        destination=destination,
        producer=producer,
        correlation_id=correlation_id,
        dedupe_key=dedupe_key,
        commit=commit,
    )
    return result if isinstance(result, uuid.UUID) else uuid.UUID(result)


async def create_public_outbox_row(
    db: AsyncSession,
    topic: str,
    payload: dict | None = None,
    *,
    headers: Optional[dict] = None,
    dedupe_key: Optional[str] = None,
    producer: Optional[str] = "msme-engine",
    correlation_id: Optional[str] = None,
    commit: bool = True,
) -> Optional[uuid.UUID]:
    """Attempt to insert into `public.outbox`.

    If the table doesn't exist the function returns None and does not raise.
    """
    if payload is None:
        payload = {}

    insert_sql = text(
        "INSERT INTO public.outbox (id, topic, payload, headers, producer, correlation_id, dedupe_key, created_at) VALUES (:id, :topic, :payload::jsonb, :headers::jsonb, :producer, :correlation_id, :dedupe_key, now()) RETURNING id"
    )

    def json_dumps(obj: Any) -> str:
        import json

        return json.dumps(obj, default=str)

    params = {
        "id": str(uuid.uuid4()),
        "topic": topic,
        "payload": json_dumps(payload),
        "headers": json_dumps(headers or {}),
        "producer": producer,
        "correlation_id": correlation_id,
        "dedupe_key": dedupe_key,
    }

    # Prefer using SQLAlchemy core insert with a Table construct for safety
    try:
        metadata = MetaData()
        public_outbox = Table("outbox", metadata, Column("id", String), schema="public")
        stmt = sa_insert(public_outbox).values(
            id=params["id"],
            topic=params["topic"],
            payload=params["payload"],
            headers=params["headers"],
            producer=params["producer"],
            correlation_id=params["correlation_id"],
            dedupe_key=params["dedupe_key"],
            created_at=func.now(),
        ).returning(public_outbox.c.id)

        res = await db.execute(stmt)
        row = res.fetchone()
        if row:
            if commit:
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
            return uuid.UUID(row[0])
    except Exception:
        await db.rollback()
        return None
