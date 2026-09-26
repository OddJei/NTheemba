"""Structured logging adapter for execution trace events."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Any

from ntheemba.observability.events import TraceEvent


class LoggingTraceSink:
    """Write each trace event as a compact structured JSON log record."""

    def __init__(
        self,
        logger: logging.Logger | None = None,
        *,
        level: int = logging.INFO,
    ) -> None:
        self._logger = logger or logging.getLogger("ntheemba.trace")
        self._level = level

    async def emit(self, event: TraceEvent) -> None:
        """Log one event without mutating its payload."""

        self._logger.log(
            self._level,
            json.dumps(self._payload(event), separators=(",", ":"), sort_keys=True),
        )

    async def emit_many(self, events: tuple[TraceEvent, ...]) -> None:
        """Log several events in their supplied order."""

        for event in events:
            await self.emit(event)

    @classmethod
    def _payload(cls, event: TraceEvent) -> dict[str, Any]:
        return {
            "attributes": cls._json_safe(event.attributes),
            "business_id": event.business_id,
            "component": event.component,
            "conversation_id": event.conversation_id,
            "duration_ms": event.duration_ms,
            "error_message": event.error_message,
            "error_type": event.error_type,
            "event_id": event.event_id,
            "message_id": event.message_id,
            "node_id": event.node_id,
            "occurred_at": event.occurred_at.isoformat(),
            "parent_span_id": event.parent_span_id,
            "request_id": event.request_id,
            "span_id": event.span_id,
            "status": event.status.value,
            "trace_id": event.trace_id,
        }

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        if value is None or isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return cls._json_safe(value.value)
        if isinstance(value, Mapping):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, tuple | list | set | frozenset):
            return [cls._json_safe(item) for item in value]
        return str(value)
