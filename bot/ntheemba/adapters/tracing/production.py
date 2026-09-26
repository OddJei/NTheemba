"""Production-safe structured-log trace exporter."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from ntheemba.observability.events import TraceEvent, TraceStatus
from ntheemba.observability.sanitization import redact_mapping


class SafeStructuredLoggingTraceSink:
    """Export redacted trace events as versioned JSON log records.

    Sampling is deterministic per trace ID so all normal lifecycle events for a
    sampled trace make the same decision. Failed events are always exported.
    Error messages are excluded by default because exception text may contain
    customer or credential data.
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        *,
        level: int = logging.INFO,
        sample_rate: float = 1.0,
        include_running: bool = True,
        include_error_messages: bool = False,
        max_error_message_length: int = 250,
    ) -> None:
        if not 0.0 <= sample_rate <= 1.0:
            raise ValueError("sample_rate must be between 0 and 1")
        if max_error_message_length < 0:
            raise ValueError("max_error_message_length must not be negative")
        self._logger = logger or logging.getLogger("ntheemba.trace")
        self._level = level
        self._sample_rate = sample_rate
        self._include_running = include_running
        self._include_error_messages = include_error_messages
        self._max_error_message_length = max_error_message_length

    async def emit(self, event: TraceEvent) -> None:
        if not self._should_export(event):
            return
        self._logger.log(
            self._level,
            json.dumps(self._payload(event), separators=(",", ":"), sort_keys=True),
        )

    async def emit_many(self, events: tuple[TraceEvent, ...]) -> None:
        for event in events:
            await self.emit(event)

    def _should_export(self, event: TraceEvent) -> bool:
        if event.status is TraceStatus.FAILED:
            return True
        if event.status is TraceStatus.RUNNING and not self._include_running:
            return False
        if self._sample_rate <= 0.0:
            return False
        if self._sample_rate >= 1.0:
            return True
        digest = hashlib.sha256(event.trace_id.encode("utf-8")).digest()
        value = int.from_bytes(digest[:8], "big") / float(2**64)
        return value < self._sample_rate

    def _payload(self, event: TraceEvent) -> dict[str, Any]:
        error_message = ""
        if self._include_error_messages and event.error_message:
            error_message = event.error_message[: self._max_error_message_length]
        return {
            "schema": "ntheemba.trace.v1",
            "attributes": redact_mapping(event.attributes),
            "business_id": event.business_id,
            "component": event.component,
            "conversation_id": event.conversation_id,
            "duration_ms": event.duration_ms,
            "error_message": error_message,
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
