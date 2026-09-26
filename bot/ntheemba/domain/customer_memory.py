"""Durable, privacy-scoped customer memory records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any


def _now() -> datetime:
    return datetime.now(UTC)


def _required(value: str, name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{name} must not be empty")
    return cleaned


class ConsentType(StrEnum):
    """Explicit customer permissions Ntheemba may rely on."""

    CROSS_BUSINESS_NAME = "cross_business_name"
    SAVED_CHECKOUT = "saved_checkout"
    MESSAGE_RETENTION = "message_retention"
    MARKETING = "marketing"


class QuestionOutcome(StrEnum):
    ANSWERED = "answered"
    PARTIAL = "partial"
    UNRESOLVED = "unresolved"
    HANDED_OVER = "handed_over"


@dataclass(frozen=True, slots=True)
class CustomerConsent:
    customer_id: str
    consent_type: ConsentType
    granted: bool
    source: str
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "customer_id", _required(self.customer_id, "customer_id"))
        object.__setattr__(self, "source", _required(self.source, "source"))
        if self.updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CustomerAddress:
    address_id: str
    customer_id: str
    label: str
    location_text: str
    business_id: str | None = None
    is_default: bool = False
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        for name in ("address_id", "customer_id", "label", "location_text"):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        if self.business_id is not None:
            object.__setattr__(self, "business_id", _required(self.business_id, "business_id"))
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CustomerPreference:
    preference_id: str
    customer_id: str
    key: str
    value: Mapping[str, Any]
    source: str
    business_id: str | None = None
    confirmed_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        for name in ("preference_id", "customer_id", "key", "source"):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        if self.business_id is not None:
            object.__setattr__(self, "business_id", _required(self.business_id, "business_id"))
        if self.confirmed_at.tzinfo is None:
            raise ValueError("confirmed_at must be timezone-aware")
        object.__setattr__(self, "value", MappingProxyType(dict(self.value)))


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    message_id: str
    conversation_id: str
    business_id: str
    customer_id: str
    sender_type: str
    message_text: str
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        for name in (
            "message_id", "conversation_id", "business_id", "customer_id",
            "sender_type", "message_text",
        ):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        if self.sender_type not in {"customer", "assistant", "human", "system"}:
            raise ValueError("sender_type is invalid")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    summary_id: str
    conversation_id: str
    business_id: str
    customer_id: str
    intent: str
    outcome: str
    topic: str = ""
    follow_up_required: bool = False
    summary: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        for name in (
            "summary_id", "conversation_id", "business_id", "customer_id", "intent", "outcome"
        ):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        object.__setattr__(self, "summary", MappingProxyType(dict(self.summary)))


@dataclass(frozen=True, slots=True)
class CustomerQuestion:
    question_id: str
    business_id: str
    customer_id: str
    conversation_id: str
    topic: str
    question_text: str
    outcome: QuestionOutcome
    required_handover: bool = False
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        for name in (
            "question_id", "business_id", "customer_id", "conversation_id", "topic", "question_text"
        ):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class RetentionResult:
    messages_deleted: int = 0
    summaries_deleted: int = 0
    questions_deleted: int = 0
    unsupported_observations_deleted: int = 0
