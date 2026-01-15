from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON as SqliteJson
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

    meta: Mapped[dict] = mapped_column(SqliteJson, default=dict)
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
    meta: Mapped[dict] = mapped_column(SqliteJson, default=dict)

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

    meta: Mapped[dict] = mapped_column(SqliteJson, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("scope", "key", name="uq_idem_scope_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope: Mapped[str] = mapped_column(String(128), index=True)
    key: Mapped[str] = mapped_column(String(128), index=True)
    status_code: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict] = mapped_column(SqliteJson, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
