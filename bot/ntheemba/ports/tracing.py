"""Technology-independent execution tracing port."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ntheemba.observability.events import TraceEvent


class TraceSink(Protocol):
    """Receive ordered, redacted execution trace events."""

    async def emit(self, event: TraceEvent) -> None:
        """Emit one trace event."""

    async def emit_many(self, events: tuple[TraceEvent, ...]) -> None:
        """Emit several trace events in order."""
