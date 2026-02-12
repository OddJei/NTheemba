"""Postgres JSONB models for ICE service state persistence."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import Column, DateTime, String, Text, JSON, Index, UUID as SQLALCHEMY_UUID
from sqlalchemy.ext.declarative import declarative_base
from uuid import uuid4

Base = declarative_base()


class IceSession(Base):
    """Session blob storage (user state, cart, preferences)."""
    __tablename__ = "ice_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String, nullable=False, unique=True, index=True)
    phone_number = Column(String, nullable=False, index=True)
    business_id = Column(String, nullable=False, index=True)
    
    # JSONB blob: session state, user context, preferences
    blob = Column(JSON, nullable=False, default={})
    
    # Metadata
    schema_version = Column(String, default="1.0")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index("ix_ice_sessions_business_id", "business_id"),
        Index("ix_ice_sessions_phone_number", "phone_number"),
    )


class IceOrderDraft(Base):
    """Order draft and out-of-band (OOB) state."""
    __tablename__ = "ice_order_drafts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String, nullable=False, index=True)
    order_id = Column(String, nullable=True, index=True)  # Set after order confirmed
    
    # JSONB blob: cart items, selections, pricing, status
    blob = Column(JSON, nullable=False, default={})
    
    # Status tracking
    status = Column(String, default="draft", index=True)  # draft, reserved, confirmed, failed
    schema_version = Column(String, default="1.0")
    
    # Idempotency
    idempotency_key = Column(String, nullable=True, unique=True, index=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index("ix_ice_order_drafts_session_id", "session_id"),
        Index("ix_ice_order_drafts_order_id", "order_id"),
    )


class IceProductSnapshot(Base):
    """Product snapshot cache for pricing and availability."""
    __tablename__ = "ice_product_snapshots"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    business_id = Column(String, nullable=False, index=True)
    product_id = Column(String, nullable=False, index=True)
    variant_id = Column(String, nullable=True, index=True)
    
    # JSONB blob: product data, price, availability, media_urls
    blob = Column(JSON, nullable=False, default={})
    
    # Metadata
    schema_version = Column(String, default="1.0")
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index("ix_product_snapshots_business_product", "business_id", "product_id"),
    )


class IceCatalogSnapshot(Base):
    """Catalog snapshot for entire business."""
    __tablename__ = "ice_catalog_snapshots"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    business_id = Column(String, nullable=False, unique=True, index=True)
    
    # JSONB blob: products list, variants, inventory, metadata
    blob = Column(JSON, nullable=False, default={})
    
    # Metadata
    schema_version = Column(String, default="1.0")
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class IceAffiliateContext(Base):
    """Affiliate context and commission tracking."""
    __tablename__ = "ice_affiliate_contexts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String, nullable=False, index=True)
    order_id = Column(String, nullable=True, index=True)
    affiliate_id = Column(String, nullable=True, index=True)
    
    # JSONB blob: affiliate info, commission rate, conversion status
    blob = Column(JSON, nullable=False, default={})
    
    # Status
    status = Column(String, default="pending", index=True)  # pending, attributed, paid
    
    # Metadata
    schema_version = Column(String, default="1.0")
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class IceAuditLog(Base):
    """Audit trail for all ICE operations."""
    __tablename__ = "ice_audit_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    
    # Context
    session_id = Column(String, nullable=False, index=True)
    order_id = Column(String, nullable=True, index=True)
    business_id = Column(String, nullable=True, index=True)
    
    # Event
    event_type = Column(String, nullable=False, index=True)  # session_created, order_confirmed, etc.
    event_payload = Column(JSON, nullable=True)
    
    # Tracing
    correlation_id = Column(String, nullable=True, index=True)
    idempotency_key = Column(String, nullable=True, index=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        Index("ix_audit_logs_session_id", "session_id"),
        Index("ix_audit_logs_event_type", "event_type"),
        Index("ix_audit_logs_created_at", "created_at"),
    )


class IceIdempotencyCache(Base):
    """Idempotency response cache for replay."""
    __tablename__ = "ice_idempotency_cache"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    idempotency_key = Column(String, nullable=False, unique=True, index=True)
    
    # Request/Response
    request_method = Column(String, nullable=False)  # POST, PUT, DELETE
    request_path = Column(String, nullable=False)
    response_status = Column(String, nullable=False)
    response_body = Column(JSON, nullable=False)
    
    # TTL (24 hours)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class IceMessageLog(Base):
    """Incoming/outgoing message pair in a single row with delivery status."""
    __tablename__ = "ice_message_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    correlation_id = Column(String, nullable=True, unique=True, index=True)
    session_id = Column(String, nullable=False, index=True)
    business_id = Column(String, nullable=True, index=True)
    user_phone = Column(String, nullable=True, index=True)
    bot_phone = Column(String, nullable=True, index=True)

    incoming_message = Column(Text, nullable=True)
    incoming_payload = Column(JSON, nullable=True)
    incoming_at = Column(DateTime(timezone=True), nullable=True)

    outgoing_message = Column(Text, nullable=True)
    outgoing_payload = Column(JSON, nullable=True)
    outgoing_status = Column(String, nullable=True, index=True)  # pending | sent | failed
    outgoing_at = Column(DateTime(timezone=True), nullable=True)
    provider_message_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
