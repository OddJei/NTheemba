"""Typed interpretation results produced before workflow authorization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from types import MappingProxyType
from typing import Any

from ntheemba.domain.enums import (
    FulfilmentMethod,
    IntentType,
    ItemType,
    MessageRole,
    RelativeSize,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class EntitySet:
    query: str | None = None
    selection: str | int | None = None
    quantity: int | None = None
    fulfilment_method: FulfilmentMethod | None = None
    delivery_details: str | None = None
    preferred_date: date | None = None
    start_time: time | None = None
    staff_id: str | None = None
    customer_name: str | None = None
    contact_number: str | None = None
    item_type: ItemType | None = None
    brand: str | None = None
    product_family: str | None = None
    variant: str | None = None
    relative_size: RelativeSize | None = None
    barcode: str | None = None
    raw_text: str = ""
    extras: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.quantity is not None and self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        object.__setattr__(self, "extras", MappingProxyType(dict(self.extras)))


@dataclass(frozen=True, slots=True)
class Intent:
    type: IntentType
    role: MessageRole
    confidence: float
    entities: EntitySet = field(default_factory=EntitySet)
    reasoning_code: str = ""

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between zero and one")


@dataclass(frozen=True, slots=True)
class PendingQuestion:
    prompt: str
    expected_intents: frozenset[IntentType]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        prompt = self.prompt.strip()
        if not prompt:
            raise ValueError("pending question prompt must not be empty")
        if not self.expected_intents:
            raise ValueError("pending question must expect at least one intent")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        object.__setattr__(self, "prompt", prompt)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
