from __future__ import annotations

import uuid
import os
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from libs.outbox.outbox import create_outbox_row


async def emit_order_delivered_outbox(
    db: AsyncSession,
    *,
    order_id: str,
    occurred_at: str,
    business_id: Optional[str] = None,
    buyer_phone: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    dedupe_key: Optional[str] = None,
) -> str:
    """Enqueue an Outbox row targeting Order-Delivery `POST /events/order/delivered`.

    Returns the created outbox `id`.
    """
    base = os.getenv("ORDER_DELIVERY_URL") or "http://order-delivery:8560"
    base = base.rstrip("/")
    destination = f"{base}/events/order/delivered"

    out_id = str(uuid.uuid4())
    await create_outbox_row(
        db,
        "order.delivered",
        {
            "order_id": order_id,
            "occurred_at": occurred_at,
            "business_id": business_id,
            "buyer_phone": buyer_phone,
            "meta": meta or {},
        },
        id=out_id,
        destination=destination,
        idempotency_key=dedupe_key,
        producer="affiliate-engine",
    )
    await db.commit()
    return out_id
