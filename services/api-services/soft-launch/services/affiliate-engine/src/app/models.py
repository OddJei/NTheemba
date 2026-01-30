from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON as SqliteJson
from sqlalchemy.sql.schema import Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Affiliate(Base):
    __tablename__ = "affiliates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    links: Mapped[list["AffiliateLink"]] = relationship(back_populates="affiliate")


class AffiliateLink(Base):
    __tablename__ = "affiliate_links"
    __table_args__ = (UniqueConstraint("code", name="uq_affiliate_link_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    affiliate_id: Mapped[str] = mapped_column(String(36), ForeignKey("affiliates.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    campaign: Mapped[str | None] = mapped_column(String(120), nullable=True)
    product_id: Mapped[str] = mapped_column(String(36), index=True)
    business_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    affiliate: Mapped[Affiliate] = relationship(back_populates="links")


class AffiliateToken(Base):
    __tablename__ = "affiliate_tokens"
    __table_args__ = (
        UniqueConstraint("token", name="uq_affiliate_token"),
        Index("ix_affiliate_tokens_token", "token"),
        Index("ix_affiliate_tokens_expires", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Short-lived token exchanged via WhatsApp message.
    token: Mapped[str] = mapped_column(String(120), nullable=False)

    link_id: Mapped[str] = mapped_column(String(36), ForeignKey("affiliate_links.id"), index=True)
    affiliate_id: Mapped[str] = mapped_column(String(36), ForeignKey("affiliates.id"), index=True)
    product_id: Mapped[str] = mapped_column(String(36), index=True)
    business_id: Mapped[str] = mapped_column(String(36), index=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    meta: Mapped[dict | None] = mapped_column(SqliteJson, nullable=True)


class AffiliateClick(Base):
    __tablename__ = "affiliate_clicks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    link_id: Mapped[str] = mapped_column(String(36), ForeignKey("affiliate_links.id"), index=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_phone: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    meta: Mapped[dict | None] = mapped_column(SqliteJson, nullable=True)


class AffiliateAttribution(Base):
    __tablename__ = "affiliate_attributions"
    __table_args__ = (UniqueConstraint("order_id", name="uq_affiliate_attribution_order_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    affiliate_id: Mapped[str] = mapped_column(String(36), ForeignKey("affiliates.id"), index=True)
    link_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("affiliate_links.id"), nullable=True)
    click_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("affiliate_clicks.id"), nullable=True)

    order_id: Mapped[str] = mapped_column(String(36), index=True)
    business_id: Mapped[str] = mapped_column(String(36), index=True)

    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_phone: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(30), default="attributed")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AffiliateEarning(Base):
    __tablename__ = "affiliate_earnings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    affiliate_id: Mapped[str] = mapped_column(String(36), ForeignKey("affiliates.id"), index=True)

    order_id: Mapped[str] = mapped_column(String(36), index=True)
    payment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="ZMW")

    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending -> ready
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AffiliateEvent(Base):
    __tablename__ = "affiliate_events"
    __table_args__ = (
        Index("ix_affiliate_events_affiliate_time", "affiliate_id", "occurred_at"),
        Index("ix_affiliate_events_type_time", "event_type", "occurred_at"),
        Index("ix_affiliate_events_order", "order_id"),
        Index("ix_affiliate_events_buyer_phone", "buyer_phone"),
        Index("ix_affiliate_events_dispatched", "dispatched_at"),
        Index("ix_affiliate_events_delivered", "delivered_at"),
    )

    # Producer-provided explicit event id.
    event_id: Mapped[str] = mapped_column(String(80), primary_key=True)

    affiliate_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("affiliates.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    source: Mapped[str | None] = mapped_column(String(60), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    buyer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    business_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    delivered_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    amount_zmw: Mapped[float | None] = mapped_column(Float, nullable=True)

    meta: Mapped[dict | None] = mapped_column("metadata", SqliteJson, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Outbox processing marker. Null means not yet dispatched.
    dispatched_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
        Index("ix_idempotency_scope_key", "scope", "key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope: Mapped[str] = mapped_column(String(200), index=True)
    key: Mapped[str] = mapped_column(String(200), index=True)

    status_code: Mapped[int] = mapped_column(default=200)
    response_json: Mapped[dict] = mapped_column(SqliteJson)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommissionSettings(Base):
    __tablename__ = "commission_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    pool_pct: Mapped[float] = mapped_column(Float, default=0.10)
    epoch_days: Mapped[int] = mapped_column(Integer, default=182)

    # Weights sum to 1.0.
    # Default OP weights: sales 50%, unique buyers 20%, MSME referrals 20%, conversion quality 10%.
    weights: Mapped[dict] = mapped_column(
        SqliteJson,
        default=lambda: {
            "sales_volume": 0.5,
            "unique_buyers": 0.2,
            "msme_referrals": 0.2,
            "conversion_quality": 0.1,
        },
    )

    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AffiliateTier(Base):
    __tablename__ = "affiliate_tiers"

    name: Mapped[str] = mapped_column(String(30), primary_key=True)
    multiplier: Mapped[float] = mapped_column(Float)
    price_zmw: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(default=True)


class AffiliateTierAssignment(Base):
    __tablename__ = "affiliate_tier_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    affiliate_id: Mapped[str] = mapped_column(String(36), ForeignKey("affiliates.id"), index=True)
    tier_name: Mapped[str] = mapped_column(String(30), ForeignKey("affiliate_tiers.name"), index=True)

    starts_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ends_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PoolEpoch(Base):
    __tablename__ = "pool_epochs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    starts_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ends_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|closed

    gross_revenue_zmw: Mapped[float] = mapped_column(Float, default=0.0)
    pool_pct: Mapped[float] = mapped_column(Float, default=0.10)
    pool_amount_zmw: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PoolAllocation(Base):
    __tablename__ = "pool_allocations"
    __table_args__ = (
        UniqueConstraint("epoch_id", "affiliate_id", name="uq_pool_alloc_epoch_aff"),
        Index("ix_pool_alloc_epoch", "epoch_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    epoch_id: Mapped[str] = mapped_column(String(36), ForeignKey("pool_epochs.id"), index=True)
    affiliate_id: Mapped[str] = mapped_column(String(36), ForeignKey("affiliates.id"), index=True)

    tier_name: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tier_multiplier: Mapped[float] = mapped_column(Float, default=1.0)

    metrics: Mapped[dict] = mapped_column(SqliteJson)
    weighted_score: Mapped[float] = mapped_column(Float)
    payout_zmw: Mapped[float] = mapped_column(Float)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
