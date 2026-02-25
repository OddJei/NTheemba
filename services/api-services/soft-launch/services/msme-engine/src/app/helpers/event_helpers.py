from __future__ import annotations

import uuid
import os
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession


async def emit_payment_success_outbox(
    db: AsyncSession,
    *,
    event_id: str,
    occurred_at: str,
    business_id: str,
    amount: float,
    currency: str,
    user_phone: Optional[str] = None,
    payment_id: Optional[str] = None,
    earnings: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> str:
    """Create an `OutboxEvent` targeting Affiliate Engine `POST /events/payment-success`.

    Returns the OutboxEvent id.
    """
    from src.app.helpers.outbox.outbox import create_outbox_row
    from src.app.config import get_pg_schema

    base = os.getenv("AFFILIATE_ENGINE_BASE_URL") or "http://affiliate-engine:8510"
    base = base.rstrip("/")
    target = f"{base}/events/payment-success"

    out_id = str(uuid.uuid4())
    schema = get_pg_schema()
    table = f"{schema}.outbox_events"
    await create_outbox_row(
        db,
        "payment_success",
        {
            "event_id": event_id,
            "event_type": "payment_success",
            "occurred_at": occurred_at,
            "producer": "msme-engine",
            "business_id": business_id,
            "amount": amount,
            "currency": currency,
            "user_phone": user_phone,
            "payment_id": payment_id,
            "earnings": earnings or {},
            "correlation_id": correlation_id,
        },
        id=out_id,
        destination=target,
        table=table,
        correlation_id=correlation_id,
        idempotency_key=out_id,
    )

    await db.commit()
    return out_id
