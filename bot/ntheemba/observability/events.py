"""Immutable execution-trace event contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import uuid4


class TraceStatus(StrEnum):
    """Lifecycle state of one traced execution node."""

    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """Redacted lifecycle event for one execution node."""

    trace_id: str
    span_id: str
    node_id: str
    component: str
    status: TraceStatus
    parent_span_id: str = ""
    request_id: str = ""
    business_id: str = ""
    conversation_id: str = ""
    message_id: str = ""
    event_id: str = field(default_factory=lambda: f"TRC-{uuid4()}")
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    duration_ms: float | None = None
    error_type: str = ""
    error_message: str = ""
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "node_id": self.node_id,
            "component": self.component,
            "event_id": self.event_id,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("duration_ms must not be negative")
        if self.status is TraceStatus.RUNNING and self.duration_ms is not None:
            raise ValueError("running events must not contain duration_ms")
        if self.status is TraceStatus.FAILED and not self.error_type.strip():
            raise ValueError("failed events must include error_type")
        if self.status is not TraceStatus.FAILED and (
            self.error_type.strip() or self.error_message.strip()
        ):
            raise ValueError("only failed events may include error details")
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))
