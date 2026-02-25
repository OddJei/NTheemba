from __future__ import annotations

from typing import Optional
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("msme_engine.helpers.payment_helpers")


async def emit_subscription_deposit_request(
    db: AsyncSession,
    *,
    business_id: str,
    subscription_id: Optional[str] = None,
    amount_minor: int,
    currency: str = "ZMW",
    phone: Optional[str] = None,
    correlation_id: Optional[str] = None,
    initiator_id: Optional[str] = None,
) -> str:
    """Create a PaymentInitiation and MsmeEvent for a subscription deposit request.

    The `MsmeEvent` will be left for the msme-engine dispatcher to post to the
    configured EVENT_SINK. Returns the created `event_id`.
    """
    from src.app.models import PaymentInitiation, MsmeEvent, utcnow

    eid = str(uuid.uuid4())
    now = utcnow()

    payload = {
        "business_id": business_id,
        "subscription_id": subscription_id,
        "amount_minor": int(amount_minor),
        "currency": currency,
        "phone": phone,
        "correlation_id": correlation_id,
        "initiator_id": initiator_id,
    }

    pi = PaymentInitiation(
        deposit_id=str(uuid.uuid4()),
        business_id=business_id,
        subscription_id=subscription_id,
        affiliate_id=None,
        meta=payload,
        status="pending",
        created_at=now,
    )
    db.add(pi)

    ev = MsmeEvent(
        event_id=eid,
        business_id=business_id,
        event_type="subscription_deposit_requested",
        occurred_at=now,
        source="msme_engine",
        correlation_id=correlation_id,
        meta=payload,
    )
    db.add(ev)

    # Also enqueue an Outbox row so the local outbox dispatcher can post
    # the deposit initiation to Payment-Revenue. Best-effort.
    try:
        from src.app.helpers.outbox.outbox import create_outbox_row
        from src.app.config import get_payment_revenue_base_url, get_pg_schema
        from src.app.helpers.outbox.schemas import DepositRequested

        dest_base = (get_payment_revenue_base_url() or "http://127.0.0.1:8590").rstrip('/')
        target = f"{dest_base}/pawapay/deposits/initiate"

        # Build and validate canonical outbox payload using shared schema
        pawapay_model = DepositRequested(
            subscription_id=subscription_id,
            business_id=business_id,
            amount_minor=int(amount_minor),
            currency=currency,
            phoneNumber=phone,
            paymentType="subscription",
            metadata={"source": "msme_engine", "correlation_id": correlation_id, "initiator_id": initiator_id},
        )

        out_id = str(uuid.uuid4())
        logger.info("creating_outbox_row", extra={"out_id": out_id, "target": target})
        # High-visibility unique trace for debugging; includes business and
        # subscription ids so we can correlate in logs across services.
        try:
            print(f"TRACE-OUTBOX-CALLED id={out_id} business={business_id} subscription={subscription_id}", flush=True)
            print(f"EMIT-OUTBOX-TRY id={out_id} target={target}", flush=True)
        except Exception:
            pass
        schema = get_pg_schema()
        table = f"{schema}.outbox_events"
        # Structured log at call site so we can confirm the helper invocation
        try:
            logger.info("calling_create_outbox_row", extra={"out_id": out_id, "table": table, "topic": "deposit_requested", "payload_keys": len(pawapay_model.model_dump() or {})})
        except Exception:
            pass
        out_inserted_id = await create_outbox_row(db, "deposit_requested", pawapay_model.model_dump(), id=out_id, destination=target, correlation_id=correlation_id, idempotency_key=out_id, table=table)
        try:
            print(f"EMIT-OUTBOX-DONE id={out_id}", flush=True)
        except Exception:
            pass
        logger.info("created_outbox_row_attempt", extra={"out_id": out_id, "out_inserted_id": out_inserted_id})
        # Tests and some local environments expect a legacy `outbox_events` ORM row.
        # Insert a compatible `OutboxEvent` ORM object as a best-effort fallback so
        # both the canonical `public.outbox` and legacy `outbox_events` consumers
        # can observe the emission in different environments.
        try:
            from src.app.models import OutboxEvent, utcnow as _utcnow

            # OutboxEvent.id is now a string column; ensure we pass a string
            oe = OutboxEvent(
                id=str(out_id),
                event_type="deposit_requested",
                payload=pawapay_model.model_dump(),
                target=target,
                status="pending",
                attempts=0,
                scheduled_at=None,
                created_at=_utcnow(),
            )
            db.add(oe)
            logger.info("added_legacy_outbox_event", extra={"out_id": out_id})
        except Exception:
            logger.exception("add_legacy_outbox_event_failed")
    except Exception:
        logger.exception("emit_outbox_failed")

    await db.commit()
    return eid
