from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON as SqliteJson
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.schema import Index

from .db import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("name", name="uq_role_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(40), index=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_user_username"),
        UniqueConstraint("email", name="uq_user_email"),
        Index("ix_user_phone", "phone"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    username: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    password_hash: Mapped[str] = mapped_column(String(400))
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id"), index=True)

    business_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    affiliate_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_user", "user_id"), Index("ix_auth_sessions_token", "token"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)

    # For soft-launch we store refresh token directly for revocation.
    token: Mapped[str] = mapped_column(String(2048))

    issued_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    device_info: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)


class VerificationToken(Base):
    __tablename__ = "verification_tokens"
    __table_args__ = (Index("ix_verification_token", "token"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(String(200), index=True)
    type: Mapped[str] = mapped_column(String(10))  # email|sms
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Business(Base):
    __tablename__ = "businesses"
    __table_args__ = (
        Index("ix_business_owner", "owner_id"),
        Index("ix_business_affiliate", "affiliate_code"),
        Index("ix_business_referred", "referred_by_msme_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)

    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(400), nullable=True)

    affiliate_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    referred_by_msme_code: Mapped[str | None] = mapped_column(String(80), nullable=True)

    subscription_plan: Mapped[str | None] = mapped_column(String(60), nullable=True)
    subscription_expiry: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    subscription_price_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subscription_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    delivery_locations: Mapped[dict | None] = mapped_column(SqliteJson, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(SqliteJson, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class BusinessSubscription(Base):
    __tablename__ = "business_subscriptions"
    __table_args__ = (Index("ix_subscription_business", "business_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)

    plan: Mapped[str] = mapped_column(String(60))
    start_date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="pending_payment")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SubscriptionReminder(Base):
    __tablename__ = "subscription_reminders"
    __table_args__ = (Index("ix_subscription_reminder_business", "business_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id: Mapped[str] = mapped_column(String(36), index=True)

    reminders_sent: Mapped[int] = mapped_column(Integer, default=0)
    last_reminder_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_pay_attempted: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MsmeCode(Base):
    __tablename__ = "msme_codes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_msme_code"),
        Index("ix_msme_code_business", "business_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)

    code: Mapped[str] = mapped_column(String(80), index=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    max_usage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(200), nullable=True)


class MsmeEvent(Base):
    __tablename__ = "msme_events"
    __table_args__ = (
        Index("ix_msme_events_business_time", "business_id", "occurred_at"),
        Index("ix_msme_events_type_time", "event_type", "occurred_at"),
    )

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    business_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    source: Mapped[str | None] = mapped_column(String(60), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    meta: Mapped[dict | None] = mapped_column("metadata", SqliteJson, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
