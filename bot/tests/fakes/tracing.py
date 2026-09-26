"""Tracing fakes used by observability integration tests."""

from __future__ import annotations

from ntheemba.observability.events import TraceEvent


class InMemoryTraceSink:
    """Record trace events in emission order."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    async def emit(self, event: TraceEvent) -> None:
        self.events.append(event)

    async def emit_many(self, events: tuple[TraceEvent, ...]) -> None:
        self.events.extend(events)
