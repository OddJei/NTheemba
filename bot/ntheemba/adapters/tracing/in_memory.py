"""In-memory trace storage for tests and the developer console."""

from __future__ import annotations

from asyncio import Lock

from ntheemba.observability.events import TraceEvent


class InMemoryTraceSink:
    """Store ordered trace events in process memory.

    This adapter is intentionally bounded so a long-running development process
    cannot grow memory without limit. It is suitable for tests and the local
    developer console, not durable production storage.
    """

    def __init__(self, *, max_events: int = 10_000) -> None:
        if max_events < 1:
            raise ValueError("max_events must be at least 1")
        self._max_events = max_events
        self._events: list[TraceEvent] = []
        self._lock = Lock()

    @property
    def max_events(self) -> int:
        """Return the configured retention limit."""

        return self._max_events

    async def emit(self, event: TraceEvent) -> None:
        """Append one event while preserving bounded insertion order."""

        async with self._lock:
            self._events.append(event)
            overflow = len(self._events) - self._max_events
            if overflow > 0:
                del self._events[:overflow]

    async def emit_many(self, events: tuple[TraceEvent, ...]) -> None:
        """Append several events atomically and in their supplied order."""

        if not events:
            return
        async with self._lock:
            self._events.extend(events)
            overflow = len(self._events) - self._max_events
            if overflow > 0:
                del self._events[:overflow]

    async def snapshot(self) -> tuple[TraceEvent, ...]:
        """Return an immutable snapshot of all retained events."""

        async with self._lock:
            return tuple(self._events)

    async def events_for_trace(self, trace_id: str) -> tuple[TraceEvent, ...]:
        """Return retained events belonging to one trace in emission order."""

        if not trace_id.strip():
            raise ValueError("trace_id must not be empty")
        async with self._lock:
            return tuple(event for event in self._events if event.trace_id == trace_id)

    async def events_for_conversation(self, conversation_id: str) -> tuple[TraceEvent, ...]:
        """Return retained events belonging to one conversation."""

        if not conversation_id.strip():
            raise ValueError("conversation_id must not be empty")
        async with self._lock:
            return tuple(
                event for event in self._events if event.conversation_id == conversation_id
            )

    async def clear(self) -> None:
        """Remove all retained events."""

        async with self._lock:
            self._events.clear()
