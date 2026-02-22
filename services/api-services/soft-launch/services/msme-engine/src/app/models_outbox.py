from __future__ import annotations

import uuid
from sqlalchemy import Column, Integer, Text, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = {"schema": "msme_engine"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target = Column(String(200))
    status = Column(String(30), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    scheduled_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    topic = Column(Text)
    destination = Column(Text)
    headers = Column(JSONB)
    producer = Column(Text)
    correlation_id = Column(Text)
    dedupe_key = Column(Text)
    last_error = Column(Text)
    last_response = Column(JSONB)
    priority = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
