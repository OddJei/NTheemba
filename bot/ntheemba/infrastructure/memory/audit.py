"""In-process structured audit sink for tests and memory-mode runtimes."""

from __future__ import annotations

from ntheemba.ports.audit import AuditEvent


class MemoryAuditSink:
    """Keep audit events in process order without external side effects."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def record(self, event: AuditEvent) -> None:
        self.events.append(event)

    async def record_many(self, events: tuple[AuditEvent, ...]) -> None:
        self.events.extend(events)
