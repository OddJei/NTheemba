from __future__ import annotations

import uuid
import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Enum, Text, UniqueConstraint, Index, JSON, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
# Provide compatibility fallbacks for SQLAlchemy versions that don't expose
# the `Mapped` typing alias or `mapped_column` helper (older SQLAlchemy).
if TYPE_CHECKING:
    from sqlalchemy.orm import Mapped, mapped_column
else:
    try:
        from sqlalchemy.orm import Mapped, mapped_column
    except Exception:  # pragma: no cover - fallback for older SQLAlchemy
        from typing import Any as _Any

        # Provide a minimal `Mapped` placeholder that supports subscription
        # (e.g. `Mapped[str]`) used in type annotations. We return `_Any` for
        # all subscriptions so the annotations remain permissive at runtime.
        class _Mapped:  # pragma: no cover - runtime fallback
            def __class_getitem__(cls, item):
                return _Any

        Mapped = _Mapped

        def _mapped_column(*args, **kwargs) -> _Any:
            """Fallback for `mapped_column` — return a regular Column.

            This allows the codebase to run against older SQLAlchemy versions
            that don't provide `mapped_column`. Type annotations using `Mapped`
            will be treated as permissive `_Any` in that case.
            """

            return Column(*args, **kwargs)

        # Expose `mapped_column` name but keep a permissive typing to satisfy
        # static type-checkers which expect a different return type from the
        # real SQLAlchemy `mapped_column` implementation.
        mapped_column: _Any = _mapped_column  # type: ignore
from sqlalchemy.ext.mutable import MutableDict
from .db import Base


class BotType(enum.Enum):
    default = "default"
    custom = "custom"


# SessionMode removed (legacy)


class SessionStatus(enum.Enum):
    active = "active"
    inactive = "inactive"
    closed = "closed"


class SessionState(enum.Enum):
    chat = "chat"
    cart = "cart"
    order = "order"
    payment = "payment"
    delivery = "delivery"
    closed = "closed"


def gen_uuid():
    return str(uuid.uuid4())


class Bot(Base):
    __tablename__ = "bots"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_uuid())
    phone_number: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    type: Mapped[BotType] = mapped_column(Enum(BotType), nullable=False)
    business_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Optimistic concurrency control for session updates
    version = Column(Integer, nullable=False, default=1)

    __mapper_args__ = {"version_id_col": version}


class Session(Base):
    __tablename__ = "sessions"

    __table_args__ = (
        UniqueConstraint('user_phone', 'bot_id', 'platform', name='uq_sessions_user_phone_bot_platform'),
        Index('ix_sessions_user_phone', 'user_phone'),
        Index('ix_sessions_platform', 'platform'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_uuid())
    user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_phone: Mapped[str] = mapped_column(String, nullable=False)
    bot_id: Mapped[str] = mapped_column(String, ForeignKey("bots.id"), nullable=False)
    business_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bot_type: Mapped[BotType] = mapped_column(Enum(BotType), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    # `state` records the current logical stage of the session. Use
    # `SessionStateCycle` records to track the start/completion of each stage and
    # preserve affiliate attribution per-cycle (so attribution is tied to the
    # user's lifecycle segment rather than the Session row).
    state: Mapped[SessionState] = mapped_column(Enum(SessionState), nullable=False, default=SessionState.chat)
    # Timestamp when the session entered the current `state`.
    state_entered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    inactive_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_node: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_event_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    object_context: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")),
        default=dict,
        nullable=True,
    )
    # affiliate attribution is stored per-cycle in SessionStateCycle
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), nullable=False, default=SessionStatus.active)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bot = relationship("Bot")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_uuid())
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False)
    user_phone: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    last_event_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    message_count = Column(Integer, default=1)
    event_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    payload_events: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")),
        nullable=True,
    )
    previous_turns: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")),
        nullable=True,
    )
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    updated_fields: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")),
        nullable=True,
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("Session")


class SessionStateCycle(Base):
    __tablename__ = "session_state_cycles"
    __table_args__ = (
        CheckConstraint(
            "(initiated_by_affiliate AND affiliate_id IS NOT NULL) OR (NOT initiated_by_affiliate AND affiliate_id IS NULL)",
            name="chk_session_state_cycles_affiliate_id",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_uuid())
    # Records one lifecycle 'cycle' for a session (e.g. chat -> cart -> order).
    # Fields:
    # - `cycle_state`: the `SessionState` this cycle represents
    # - `started_at` / `completed_at`: timestamps for the cycle
    # - `initiated_by_affiliate` + `affiliate_*` / `meta`: attribution captured
    #   when the cycle was started (copied forward when transitions occur).
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False)
    cycle_state: Mapped[SessionState] = mapped_column(Enum(SessionState), nullable=False, default=SessionState.chat)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    initiated_by_affiliate = Column(Boolean, default=True, nullable=False)
    affiliate_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")),
        nullable=True,
    )

    session = relationship("Session")


class Outbox(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        # Allow idempotent inserts by topic+dedupe_key
        Index("ix_outbox_topic", "topic"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    dedupe_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    destination: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    headers: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    producer: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    send_after: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_response: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    priority: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
