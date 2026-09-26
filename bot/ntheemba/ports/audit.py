"""Structured audit-event port."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol
from uuid import uuid4


class AuditSeverity(StrEnum):
    """Operational importance of an audit event."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Redacted event describing an important system decision."""

    event_type: str
    request_id: str
    business_id: str
    severity: AuditSeverity = AuditSeverity.INFO
    conversation_id: str = ""
    message_id: str = ""
    event_id: str = field(default_factory=lambda: f"AUD-{uuid4()}")
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in {
            "event_type": self.event_type,
            "request_id": self.request_id,
            "business_id": self.business_id,
            "event_id": self.event_id,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))


class AuditSink(Protocol):
    """Persist structured audit events."""

    async def record(self, event: AuditEvent) -> None:
        """Record one event."""

    async def record_many(self, events: tuple[AuditEvent, ...]) -> None:
        """Record several events in order."""
