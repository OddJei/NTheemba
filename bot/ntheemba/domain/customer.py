"""Durable customer identity and privacy-aware relationship models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _clean_required(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


class ConsentType(StrEnum):
    """Customer-controlled reusable data permissions."""

    CROSS_BUSINESS_RECOGNITION = "cross_business_recognition"
    SAVED_CHECKOUT_DETAILS = "saved_checkout_details"
    MARKETING_MESSAGES = "marketing_messages"
    CONVERSATION_RETENTION = "conversation_retention"


class QuestionOutcome(StrEnum):
    """How a customer question was handled."""

    ANSWERED = "answered"
    PARTIAL = "partial"
    UNRESOLVED = "unresolved"
    HANDED_OVER = "handed_over"


@dataclass(frozen=True, slots=True)
class Customer:
    """Platform identity shared only through explicit consent rules."""

    customer_id: str
    phone_e164: str
    platform_display_name: str | None = None
    preferred_language: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    last_seen_at: datetime = field(default_factory=_utc_now)
    status: str = "active"

    def __post_init__(self) -> None:
        object.__setattr__(self, "customer_id", _clean_required(self.customer_id, "customer_id"))
        phone = self.phone_e164.strip()
        if not phone.startswith("+") or not phone[1:].isdigit():
            raise ValueError("phone_e164 must use international format")
        if not 8 <= len(phone[1:]) <= 15:
            raise ValueError("phone_e164 must contain 8 to 15 digits")
        object.__setattr__(self, "phone_e164", phone)
        if self.platform_display_name is not None:
            name = self.platform_display_name.strip()
            object.__setattr__(self, "platform_display_name", name or None)
        if self.preferred_language is not None:
            language = self.preferred_language.strip()
            object.__setattr__(self, "preferred_language", language or None)
        if self.created_at.tzinfo is None or self.last_seen_at.tzinfo is None:
            raise ValueError("customer timestamps must be timezone-aware")

    @classmethod
    def create(
        cls,
        phone_e164: str,
        *,
        display_name: str | None = None,
        preferred_language: str | None = None,
        now: datetime | None = None,
    ) -> Customer:
        moment = now or _utc_now()
        return cls(
            customer_id=f"CUST-{uuid4()}",
            phone_e164=phone_e164,
            platform_display_name=display_name,
            preferred_language=preferred_language,
            created_at=moment,
            last_seen_at=moment,
        )


@dataclass(frozen=True, slots=True)
class BusinessCustomer:
    """One business's private relationship with a platform customer."""

    business_customer_id: str
    business_id: str
    customer_id: str
    preferred_name: str | None = None
    first_seen_at: datetime = field(default_factory=_utc_now)
    last_seen_at: datetime = field(default_factory=_utc_now)
    order_count: int = 0
    booking_count: int = 0
    loyalty_status: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "business_customer_id",
            _clean_required(self.business_customer_id, "business_customer_id"),
        )
        object.__setattr__(self, "business_id", _clean_required(self.business_id, "business_id"))
        object.__setattr__(self, "customer_id", _clean_required(self.customer_id, "customer_id"))
        if self.order_count < 0 or self.booking_count < 0:
            raise ValueError("business activity counts must not be negative")
        if self.preferred_name is not None:
            name = self.preferred_name.strip()
            object.__setattr__(self, "preferred_name", name or None)
        if self.first_seen_at.tzinfo is None or self.last_seen_at.tzinfo is None:
            raise ValueError("business-customer timestamps must be timezone-aware")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def create(
        cls,
        business_id: str,
        customer_id: str,
        *,
        preferred_name: str | None = None,
        now: datetime | None = None,
    ) -> BusinessCustomer:
        moment = now or _utc_now()
        return cls(
            business_customer_id=f"BCUST-{uuid4()}",
            business_id=business_id,
            customer_id=customer_id,
            preferred_name=preferred_name,
            first_seen_at=moment,
            last_seen_at=moment,
        )


@dataclass(frozen=True, slots=True)
class CustomerConsent:
    customer_id: str
    consent_type: ConsentType
    granted: bool
    source: str
    updated_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "customer_id", _clean_required(self.customer_id, "customer_id"))
        object.__setattr__(self, "source", _clean_required(self.source, "source"))
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
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        for field_name in ("address_id", "customer_id", "label", "location_text"):
            object.__setattr__(
                self,
                field_name,
                _clean_required(getattr(self, field_name), field_name),
            )
        if self.business_id is not None:
            object.__setattr__(
                self,
                "business_id",
                _clean_required(self.business_id, "business_id"),
            )
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CustomerPreference:
    preference_id: str
    customer_id: str
    key: str
    value: Mapping[str, Any]
    business_id: str | None = None
    source: str = "customer"
    confirmed_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        for field_name in ("preference_id", "customer_id", "key", "source"):
            object.__setattr__(
                self,
                field_name,
                _clean_required(getattr(self, field_name), field_name),
            )
        if self.business_id is not None:
            object.__setattr__(
                self,
                "business_id",
                _clean_required(self.business_id, "business_id"),
            )
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
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        for field_name in (
            "message_id",
            "conversation_id",
            "business_id",
            "customer_id",
            "sender_type",
            "message_text",
        ):
            object.__setattr__(
                self,
                field_name,
                _clean_required(getattr(self, field_name), field_name),
            )
        if self.sender_type not in {"customer", "assistant", "human", "system"}:
            raise ValueError("unsupported message sender_type")
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
    topic: str | None = None
    follow_up_required: bool = False
    summary: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        for field_name in (
            "summary_id",
            "conversation_id",
            "business_id",
            "customer_id",
            "intent",
            "outcome",
        ):
            object.__setattr__(
                self,
                field_name,
                _clean_required(getattr(self, field_name), field_name),
            )
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
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        for field_name in (
            "question_id",
            "business_id",
            "customer_id",
            "conversation_id",
            "topic",
            "question_text",
        ):
            object.__setattr__(
                self,
                field_name,
                _clean_required(getattr(self, field_name), field_name),
            )
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CustomerCheckoutContext:
    addresses: tuple[CustomerAddress, ...] = ()
    preferences: tuple[CustomerPreference, ...] = ()


@dataclass(frozen=True, slots=True)
class CustomerRecognition:
    """Privacy-filtered identity result suitable for one business conversation."""

    customer: Customer
    business_customer: BusinessCustomer
    display_name: str | None
    recognised_across_businesses: bool
    saved_checkout_allowed: bool
    should_ask_name: bool


@dataclass(frozen=True, slots=True)
class CustomerWorkflowContext:
    """Privacy-filtered customer details available to one workflow execution."""

    platform_customer_id: str
    phone_e164: str
    display_name: str | None = None
    recognised_across_businesses: bool = False
    platform_checkout_allowed: bool = False
    default_delivery_location: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "platform_customer_id",
            _clean_required(self.platform_customer_id, "platform_customer_id"),
        )
        phone = self.phone_e164.strip()
        if not phone.startswith("+") or not phone[1:].isdigit():
            raise ValueError("phone_e164 must use international format")
        object.__setattr__(self, "phone_e164", phone)
        if self.display_name is not None:
            name = self.display_name.strip()
            object.__setattr__(self, "display_name", name or None)
        if self.default_delivery_location is not None:
            location = self.default_delivery_location.strip()
            object.__setattr__(self, "default_delivery_location", location or None)
