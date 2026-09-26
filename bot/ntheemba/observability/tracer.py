"""Reusable span lifecycle management."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from time import monotonic
from typing import Any

from ntheemba.observability.context import (
    TraceContext,
    bind_trace_context,
    current_trace_context,
    new_trace_context,
)
from ntheemba.observability.events import TraceEvent, TraceStatus
from ntheemba.ports.tracing import TraceSink


class NullTraceSink:
    """No-op sink used when tracing is disabled."""

    async def emit(self, event: TraceEvent) -> None:
        """Discard one event."""

    async def emit_many(self, events: tuple[TraceEvent, ...]) -> None:
        """Discard several events."""


class Tracer:
    """Create correlated spans and emit their lifecycle events."""

    def __init__(
        self,
        sink: TraceSink | None = None,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._sink: TraceSink = sink or NullTraceSink()
        self._clock = clock

    @asynccontextmanager
    async def span(
        self,
        node_id: str,
        component: str,
        *,
        attributes: Mapping[str, Any] | None = None,
        root_context: TraceContext | None = None,
    ) -> AsyncIterator[TraceContext]:
        """Emit running/final events while preserving exception semantics."""

        parent = current_trace_context()
        if parent is None:
            context = root_context or new_trace_context(attributes=attributes)
        else:
            context = parent.child(attributes=attributes)

        await self._sink.emit(
            self._event(
                context=context,
                node_id=node_id,
                component=component,
                status=TraceStatus.RUNNING,
                attributes=attributes,
            )
        )
        started_at = self._clock()

        with bind_trace_context(context):
            try:
                yield context
            except Exception as error:
                duration_ms = max(0.0, (self._clock() - started_at) * 1000)
                await self._sink.emit(
                    self._event(
                        context=context,
                        node_id=node_id,
                        component=component,
                        status=TraceStatus.FAILED,
                        duration_ms=duration_ms,
                        error=error,
                        attributes=attributes,
                    )
                )
                raise
            else:
                duration_ms = max(0.0, (self._clock() - started_at) * 1000)
                await self._sink.emit(
                    self._event(
                        context=context,
                        node_id=node_id,
                        component=component,
                        status=TraceStatus.PASSED,
                        duration_ms=duration_ms,
                        attributes=attributes,
                    )
                )

    @staticmethod
    def _event(
        *,
        context: TraceContext,
        node_id: str,
        component: str,
        status: TraceStatus,
        duration_ms: float | None = None,
        error: Exception | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> TraceEvent:
        return TraceEvent(
            trace_id=context.trace_id,
            span_id=context.span_id,
            parent_span_id=context.parent_span_id,
            node_id=node_id,
            component=component,
            status=status,
            request_id=context.request_id,
            business_id=context.business_id,
            conversation_id=context.conversation_id,
            message_id=context.message_id,
            duration_ms=duration_ms,
            error_type=type(error).__name__ if error is not None else "",
            error_message=str(error) if error is not None else "",
            attributes=attributes or {},
        )
