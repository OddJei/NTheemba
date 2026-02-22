from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models import Order
from src.app.helpers.outbox.outbox import create_outbox_row
# Avoid importing from `src.app.main` at module import time to prevent
# circular imports (main imports these helpers). Import inside functions.


async def emit_deposit_request(
    db: AsyncSession,
    *,
    order_id: str,
    amount_minor: int,
    currency: str,
    phone: Optional[str] = None,
    correlation_id: Optional[str] = None,
    initiator_id: Optional[str] = None,
    initiator_role: Optional[str] = None,
    platform_fee_minor: Optional[int] = None,
) -> None:
    """Emit an outbox event requesting a customer deposit for an order.

    Records a small marker in `order.meta.deposit_request` and enqueues
    an OutboxEvent `deposit_requested` with the canonical payload.
    """
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise ValueError("order_not_found")

    from src.app.main import _utcnow, _emit_outbox

    now = _utcnow()
    meta = dict(order.meta or {})
    meta.setdefault("deposit_request", {})
    meta["deposit_request"].update({"amount_minor": int(amount_minor), "currency": currency, "requested_at": now.isoformat().replace("+00:00", "Z")})
    if phone:
        meta["deposit_request"]["phone"] = phone
    # Record who asked for this deposit
    if initiator_id:
        meta["deposit_request"]["initiator_id"] = initiator_id
    if initiator_role:
        meta["deposit_request"]["initiator_role"] = initiator_role
    order.meta = meta
    order.updated_at = now

    # Emit a payload shaped for pawaPay deposit initiation so the outbox
    # dispatcher can post directly to Payment-Revenue's `/pawapay/deposits/initiate`.
    pawapay_payload = {
        # Let the receiver (payment-revenue) derive/assign depositId via idempotency key if needed.
        "order_id": order.id,
        "business_id": order.business_id,
        "amount_minor": int(amount_minor),
        "currency": currency,
        "phoneNumber": phone,
        "paymentType": "order",
        "metadata": {"source": "order_delivery"},
    }
    if initiator_id:
        pawapay_payload["initiatorId"] = initiator_id
    if initiator_role:
        pawapay_payload["initiatorRole"] = initiator_role
    if correlation_id:
        pawapay_payload["metadata"]["correlation_id"] = correlation_id
    if platform_fee_minor is not None:
        pawapay_payload["metadata"]["platform_fee_minor"] = int(platform_fee_minor)

    out_id = str(__import__("uuid").uuid4())
    await create_outbox_row(db, "deposit_requested", pawapay_payload, id=out_id, destination=None, producer="order-delivery")


async def emit_payout_request(
    db: AsyncSession,
    *,
    order_id: str,
    amount_minor: int,
    currency: str,
    beneficiary: dict,
    correlation_id: Optional[str] = None,
    initiator_id: Optional[str] = None,
    initiator_role: Optional[str] = None,
) -> None:
    """Emit an outbox event requesting a payout for an order (msme/provider payout).

    Writes `order.meta.payout_request` and enqueues `payout_requested`.
    """
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise ValueError("order_not_found")

    from src.app.main import _utcnow, _emit_outbox

    now = _utcnow()
    meta = dict(order.meta or {})
    meta.setdefault("payout_request", {})
    meta["payout_request"].update({"amount_minor": int(amount_minor), "currency": currency, "beneficiary": beneficiary, "requested_at": now.isoformat().replace("+00:00", "Z")})
    # Record initiator
    if initiator_id:
        meta["payout_request"]["initiator_id"] = initiator_id
    if initiator_role:
        meta["payout_request"]["initiator_role"] = initiator_role
    order.meta = meta
    order.updated_at = now

    # Emit a payload shaped for MSME payout initiation so the outbox
    # dispatcher can post to Payment-Revenue's `/msme/payouts/initiate`.
    # Expect beneficiary to contain phone under 'phone' or 'msme_phone'.
    msme_phone = beneficiary.get("phone") or beneficiary.get("msme_phone") or beneficiary.get("msmePhone")
    msme_payload = {
        "order_id": order.id,
        "business_id": order.business_id,
        "msme_phone": msme_phone,
        "order_amount_minor": int(amount_minor),
        "currency": currency,
        "metadata": {"source": "order_delivery"},
    }
    if initiator_id:
        msme_payload["metadata"]["initiator_id"] = initiator_id
    if initiator_role:
        msme_payload["metadata"]["initiator_role"] = initiator_role
    if correlation_id:
        msme_payload["metadata"]["correlation_id"] = correlation_id

    out_id = str(__import__("uuid").uuid4())
    await create_outbox_row(db, "payout_requested", msme_payload, id=out_id, destination=None, producer="order-delivery")


async def emit_refund_request(
    db: AsyncSession,
    *,
    order_id: str,
    amount_minor: int,
    currency: str,
    payment_method: Optional[dict] = None,
    reason: Optional[str] = None,
    correlation_id: Optional[str] = None,
    initiator_id: Optional[str] = None,
    initiator_role: Optional[str] = None,
) -> None:
    """Emit an outbox event requesting a refund for an order.

    Writes `order.meta.refund` (status requested) and enqueues `refund_requested`.
    """
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise ValueError("order_not_found")

    from src.app.main import _utcnow, _emit_outbox

    now = _utcnow()
    meta = dict(order.meta or {})
    meta.setdefault("refund", {})
    meta["refund"].update({"status": "requested", "amount_minor": int(amount_minor), "currency": currency, "reason": reason, "initiated_at": now.isoformat().replace("+00:00", "Z")})
    if payment_method is not None:
        meta["refund"]["payment_method"] = payment_method
    if initiator_id:
        meta["refund"]["initiator_id"] = initiator_id
    if initiator_role:
        meta["refund"]["initiator_role"] = initiator_role
    order.meta = meta
    order.updated_at = now

    out_id = str(__import__("uuid").uuid4())
    await create_outbox_row(
        db,
        "refund_requested",
        {
            "order_id": order.id,
            "business_id": order.business_id,
            "amount_minor": int(amount_minor),
            "currency": currency,
            "payment_method": payment_method,
            "reason": reason,
            "correlation_id": correlation_id,
            "initiator_id": initiator_id,
            "initiator_role": initiator_role,
        },
        id=out_id,
        producer="order-delivery",
    )
