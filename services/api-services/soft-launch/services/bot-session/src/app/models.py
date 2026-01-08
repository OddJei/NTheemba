import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Enum, Text, UniqueConstraint, Index, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from .db import Base


class BotType(enum.Enum):
    default = "default"
    custom = "custom"


class SessionMode(enum.Enum):
    public = "public"
    registered = "registered"
    customer = "customer"
    staff = "staff"


class SessionStatus(enum.Enum):
    active = "active"
    inactive = "inactive"


def gen_uuid():
    return str(uuid.uuid4())


class Bot(Base):
    __tablename__ = "bots"

    id = Column(String, primary_key=True, default=gen_uuid)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    type = Column(Enum(BotType), nullable=False)
    business_id = Column(String, nullable=True, unique=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Session(Base):
    __tablename__ = "sessions"

    __table_args__ = (
        UniqueConstraint('user_phone', 'bot_id', 'platform', name='uq_sessions_user_phone_bot_platform'),
        Index('ix_sessions_user_phone', 'user_phone'),
        Index('ix_sessions_platform', 'platform'),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, nullable=True)
    user_phone = Column(String, nullable=False)
    bot_id = Column(String, ForeignKey("bots.id"), nullable=False)
    business_id = Column(String, nullable=True)
    bot_type = Column(Enum(BotType), nullable=False)
    session_mode = Column(Enum(SessionMode), nullable=False)
    platform = Column(String, nullable=False)
    current_node = Column(String, nullable=True)
    last_event_id = Column(String, nullable=True)
    object_context = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    status = Column(Enum(SessionStatus), nullable=False, default=SessionStatus.active)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bot = relationship("Bot")


class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    user_phone = Column(String, index=True, nullable=True)
    user_id = Column(String, nullable=True)
    bot_id = Column(String, nullable=False)
    last_event_id = Column(String, nullable=True)
    message_count = Column(Integer, default=1)
    event_type = Column(String, nullable=True)
    payload_events = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    previous_turns = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    status = Column(String, nullable=True)
    updated_fields = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("Session")
