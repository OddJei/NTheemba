"""Fan-out adapter for sending trace events to several sinks."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ntheemba.observability.events import TraceEvent
from ntheemba.ports.tracing import TraceSink

TraceSinkErrorHandler = Callable[[TraceSink, Exception], None]


class CompositeTraceSink:
    """Emit each event to multiple sinks in deterministic order.

    By default sink failures are isolated so observability cannot break the
    customer-message pipeline. Strict mode is available for tests and startup
    validation where surfacing adapter failures is preferable.
    """

    def __init__(
        self,
        sinks: Sequence[TraceSink],
        *,
        strict: bool = False,
        on_error: TraceSinkErrorHandler | None = None,
    ) -> None:
        if not sinks:
            raise ValueError("at least one trace sink is required")
        self._sinks = tuple(sinks)
        self._strict = strict
        self._on_error = on_error

    async def emit(self, event: TraceEvent) -> None:
        """Fan one event out to every configured sink."""

        for sink in self._sinks:
            try:
                await sink.emit(event)
            except Exception as error:
                self._handle_error(sink, error)

    async def emit_many(self, events: tuple[TraceEvent, ...]) -> None:
        """Fan a batch out to every sink while preserving batch order."""

        if not events:
            return
        for sink in self._sinks:
            try:
                await sink.emit_many(events)
            except Exception as error:
                self._handle_error(sink, error)

    def _handle_error(self, sink: TraceSink, error: Exception) -> None:
        if self._on_error is not None:
            self._on_error(sink, error)
        if self._strict:
            raise error
