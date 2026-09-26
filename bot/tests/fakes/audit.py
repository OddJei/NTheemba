"""In-memory structured audit sink."""

from __future__ import annotations

from ntheemba.ports.audit import AuditEvent


class InMemoryAuditSink:
    """Capture audit events in record order."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []
        self.fail_next = False

    async def record(self, event: AuditEvent) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("injected audit failure")
        self.events.append(event)

    async def record_many(self, events: tuple[AuditEvent, ...]) -> None:
        for event in events:
            await self.record(event)
