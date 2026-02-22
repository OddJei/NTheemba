from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.app.db import Base


def utcnow() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


class Settlement(Base):
    __tablename__ = "settlements"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_settlement_order"),
        UniqueConstraint("payment_id", name="uq_settlement_payment"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    order_id: Mapped[str] = mapped_column(String(64), index=True)
    payment_id: Mapped[str] = mapped_column(String(64), index=True)
    business_id: Mapped[str] = mapped_column(String(64), index=True)

    currency: Mapped[str] = mapped_column(String(8), default="ZMW")
    amount_minor: Mapped[int] = mapped_column(Integer)

    fee_bps: Mapped[int] = mapped_column(Integer)  # 500 or 700
    platform_fee_minor: Mapped[int] = mapped_column(Integer)
    affiliate_commission_minor: Mapped[int] = mapped_column(Integer)
    msme_net_minor: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(32), default="computed")  # computed|dispatched
    dispatched: Mapped[bool] = mapped_column(Boolean, default=False)

    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Outbox(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        # Allows idempotent event insertion when callbacks are delivered multiple times.
        UniqueConstraint("topic", "dedupe_key", name="uq_outbox_topic_dedupe_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    topic: Mapped[str] = mapped_column(String(64), index=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    destination: Mapped[str] = mapped_column(String(256))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|sent|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)

    send_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Payout(Base):
    __tablename__ = "payouts"
    __table_args__ = (
        # One payout per (order_id, payee_type) to simplify idempotency.
        UniqueConstraint("order_id", "payee_type", name="uq_payout_order_payee_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    order_id: Mapped[str] = mapped_column(String(64), index=True)
    payment_id: Mapped[str] = mapped_column(String(64), index=True)
    business_id: Mapped[str] = mapped_column(String(64), index=True)

    # "msme" | "affiliate" | "platform"
    payee_type: Mapped[str] = mapped_column(String(32), index=True)
    # For affiliate payouts we may not know affiliate_id at settlement time, so this can be null.
    payee_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    currency: Mapped[str] = mapped_column(String(8), default="ZMW")
    amount_minor: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|dispatched
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"
    __table_args__ = (
        UniqueConstraint("payment_id", name="uq_sub_payment_payment"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    payment_id: Mapped[str] = mapped_column(String(64), index=True)
    business_id: Mapped[str] = mapped_column(String(64), index=True)
    plan: Mapped[str] = mapped_column(String(32))
    paid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    currency: Mapped[str] = mapped_column(String(8), default="ZMW")
    amount_minor: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(32), default="computed")  # computed|dispatched
    dispatched: Mapped[bool] = mapped_column(Boolean, default=False)

    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("scope", "key", name="uq_idem_scope_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope: Mapped[str] = mapped_column(String(128), index=True)
    key: Mapped[str] = mapped_column(String(128), index=True)
    status_code: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PawaPayDeposit(Base):
    __tablename__ = "pawapay_deposits"
    __table_args__ = (UniqueConstraint("deposit_id", name="uq_pawapay_deposit_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deposit_id: Mapped[str] = mapped_column(String(64), index=True)

    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    business_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    currency: Mapped[str] = mapped_column(String(8), default="ZMW")
    amount_minor: Mapped[int] = mapped_column(Integer, default=0)

    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="CREATED")
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Persisted platform/payment fields
    platform_fee_minor: Mapped[int] = mapped_column(Integer, default=0)
    fee_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    msme_net_minor: Mapped[int] = mapped_column(Integer, default=0)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PawaPayPayout(Base):
    __tablename__ = "pawapay_payouts"
    __table_args__ = (UniqueConstraint("payout_id", name="uq_pawapay_payout_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payout_id: Mapped[str] = mapped_column(String(64), index=True)

    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    business_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    currency: Mapped[str] = mapped_column(String(8), default="ZMW")
    amount_minor: Mapped[int] = mapped_column(Integer, default=0)

    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="CREATED")
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(256), nullable=True)

    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    # payout_type: 'msme' | 'affiliate' - enforce non-null at DB level
    payout_type: Mapped[str] = mapped_column(String(32), default='msme')


class PawaPayRefund(Base):
    __tablename__ = "pawapay_refunds"
    __table_args__ = (UniqueConstraint("refund_id", name="uq_pawapay_refund_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    refund_id: Mapped[str] = mapped_column(String(64), index=True)
    deposit_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    business_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    currency: Mapped[str] = mapped_column(String(8), default="ZMW")
    amount_minor: Mapped[int] = mapped_column(Integer, default=0)

    # Platform fee portion that corresponds to this refund (for revenue accounting)
    platform_fee_minor: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(String(32), default="CREATED")
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(256), nullable=True)

    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MSMEPayout(Base):
    __tablename__ = "msme_payouts"
    __table_args__ = (UniqueConstraint("payout_id", name="uq_msme_payout_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payout_id: Mapped[str] = mapped_column(String(64), index=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    business_id: Mapped[str] = mapped_column(String(64), index=True)

    msme_phone: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)

    currency: Mapped[str] = mapped_column(String(8), default="ZMW")
    amount_minor: Mapped[int] = mapped_column(Integer)  # Amount paid to MSME
    platform_fee_minor: Mapped[int] = mapped_column(Integer, default=0)  # Fee retained by platform

    status: Mapped[str] = mapped_column(String(32), default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(256), nullable=True)

    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    initiated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MSMEPayoutRecord(Base):
    __tablename__ = "msme_payout_records"
    __table_args__ = (UniqueConstraint("order_id", name="uq_msme_payout_order"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    business_id: Mapped[str] = mapped_column(String(64), index=True)
    payout_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    currency: Mapped[str] = mapped_column(String(8), default="ZMW")
    order_amount_minor: Mapped[int] = mapped_column(Integer)  # Full order amount
    platform_fee_minor: Mapped[int] = mapped_column(Integer)  # Platform fee (retained)
    msme_payout_minor: Mapped[int] = mapped_column(Integer)  # Amount sent to MSME

    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|processing|completed|failed
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)

    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    initiated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AffiliatePayoutRecord(Base):
    """Record of affiliate payout initiated by affiliate-engine."""
    
    __tablename__ = "affiliate_payout_records"
    __table_args__ = (
        UniqueConstraint("payout_id", name="uq_affiliate_payout_id"),
        UniqueConstraint("batch_id", "affiliate_id", name="uq_affiliate_payout_batch_aff"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    payout_id: Mapped[str] = mapped_column(String(36), unique=True)  # Unique payout ID
    batch_id: Mapped[str] = mapped_column(String(36))  # Batch this payout belongs to
    epoch_id: Mapped[str] = mapped_column(String(36), index=True)
    affiliate_id: Mapped[str] = mapped_column(String(36), index=True)
    
    # Amount
    amount_minor: Mapped[int] = mapped_column(Integer)  # Amount in minor units (cents)
    currency: Mapped[str] = mapped_column(String(8), default="ZMW")
    
    # Status
    status: Mapped[str] = mapped_column(String(50), default="PENDING")  # PENDING|COMPLETED|FAILED
    failure_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    
    # Metadata
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Timestamps
    initiated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PlatformFee(Base):
    __tablename__ = "platform_fees"
    __table_args__ = (UniqueConstraint("deposit_id", name="uq_platform_fee_deposit"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deposit_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    currency: Mapped[str] = mapped_column(String(8), default="ZMW")
    amount_minor: Mapped[int] = mapped_column(Integer, default=0)

    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
