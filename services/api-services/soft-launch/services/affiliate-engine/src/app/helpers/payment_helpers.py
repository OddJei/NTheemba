from __future__ import annotations

from typing import Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from libs.outbox.outbox import create_outbox_row


async def emit_affiliate_payout_request(
    db: AsyncSession,
    *,
    affiliate_id: Optional[str],
    order_id: Optional[str],
    business_id: str,
    amount_zmw: float,
    currency: str = "ZMW",
    correlation_id: Optional[str] = None,
    initiator_id: Optional[str] = None,
    initiator_role: Optional[str] = None,
    event_id: Optional[str] = None,
) -> str:
    """Create an AffiliateEarning (if affiliate provided) and an AffiliateEvent.

    The created `AffiliateEvent` will be left with `dispatched_at == None` so the
    local dispatcher will pick it up and deliver to the configured event sink.
    Returns the `event_id` used.
    """
    from src.app.models import AffiliateEarning, AffiliateEvent, utcnow

    eid = event_id or str(uuid.uuid4())
    now = utcnow()

    # Record earning row for accounting/visibility (status pending)
    if affiliate_id:
        earning = AffiliateEarning(
            affiliate_id=affiliate_id,
            order_id=order_id or "",
            payment_id=None,
            amount=float(amount_zmw),
            currency=currency,
            status="pending",
            created_at=now,
        )
        db.add(earning)

    # Create an AffiliateEvent for the outbox/dispatcher
    ev = AffiliateEvent(
        event_id=eid,
        affiliate_id=affiliate_id,
        event_type="affiliate_payout_requested",
        occurred_at=now,
        source="affiliate_engine",
        correlation_id=correlation_id,
        order_id=order_id,
        business_id=business_id,
        amount_zmw=float(amount_zmw),
        meta={
            "initiator_id": initiator_id,
            "initiator_role": initiator_role,
        },
    )
    db.add(ev)

    # Also enqueue an Outbox row so the central outbox dispatcher or external
    # flusher can deliver the payout request to Payment-Revenue.
    try:
        from src.app.models import Outbox
        from src.app.config import get_payment_revenue_base_url

        dest_base = (get_payment_revenue_base_url() or "http://127.0.0.1:8590").rstrip('/')
        destination = f"{dest_base}/pawapay/payouts/initiate"

        payload = {
            "order_id": order_id,
            "business_id": business_id,
            "amount_minor": int(float(amount_zmw)),
            "currency": currency,
            "phoneNumber": None,
            "payoutType": "affiliate",
            "metadata": {
                "source": "affiliate_engine",
                "affiliate_id": affiliate_id,
                "correlation_id": correlation_id,
                "initiator_id": initiator_id,
                "initiator_role": initiator_role,
            },
        }

        if isinstance(ev.meta, dict) and ev.meta.get("phone"):
            payload["phoneNumber"] = ev.meta.get("phone")

        out_id = str(uuid.uuid4())
        await create_outbox_row(db, "payout_requested", payload, id=out_id, destination=destination, idempotency_key=eid, producer="affiliate-engine")
    except Exception:
        # don't fail the whole operation if outbox insertion is not supported
        pass

    await db.commit()
    return eid
