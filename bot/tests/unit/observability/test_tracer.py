from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from ntheemba.observability import (
    TraceEvent,
    Tracer,
    TraceStatus,
    current_trace_context,
    new_trace_context,
    trace_node,
)


@dataclass
class RecordingTraceSink:
    events: list[TraceEvent] = field(default_factory=list)

    async def emit(self, event: TraceEvent) -> None:
        self.events.append(event)

    async def emit_many(self, events: tuple[TraceEvent, ...]) -> None:
        self.events.extend(events)


class Clock:
    def __init__(self) -> None:
        self.values = iter((10.0, 10.125))

    def __call__(self) -> float:
        return next(self.values)


@pytest.mark.asyncio
async def test_span_emits_running_then_passed_and_restores_context() -> None:
    sink = RecordingTraceSink()
    tracer = Tracer(sink, clock=Clock())
    root = new_trace_context(
        request_id="request-1",
        business_id="business-1",
        conversation_id="conversation-1",
        message_id="message-1",
    )

    async with tracer.span(
        "interpret",
        "application.interpretation",
        root_context=root,
        attributes={"source": "rules"},
    ) as context:
        assert current_trace_context() is context

    assert current_trace_context() is None
    assert [event.status for event in sink.events] == [
        TraceStatus.RUNNING,
        TraceStatus.PASSED,
    ]
    assert sink.events[0].trace_id == root.trace_id
    assert sink.events[1].duration_ms == pytest.approx(125)
    assert sink.events[1].request_id == "request-1"
    assert sink.events[1].attributes == {"source": "rules"}


@pytest.mark.asyncio
async def test_nested_span_uses_parent_span() -> None:
    sink = RecordingTraceSink()
    tracer = Tracer(sink)
    root = new_trace_context()

    async with tracer.span("outer", "application.service", root_context=root) as outer:
        async with tracer.span("inner", "application.router") as inner:
            assert inner.trace_id == outer.trace_id
            assert inner.parent_span_id == outer.span_id

    inner_running = sink.events[1]
    assert inner_running.node_id == "inner"
    assert inner_running.parent_span_id == root.span_id


@pytest.mark.asyncio
async def test_span_emits_failure_and_reraises_original_exception() -> None:
    sink = RecordingTraceSink()
    tracer = Tracer(sink, clock=Clock())

    with pytest.raises(RuntimeError, match="TradeFlow unavailable"):
        async with tracer.span("tradeflow", "adapters.tradeflow"):
            raise RuntimeError("TradeFlow unavailable")

    assert [event.status for event in sink.events] == [
        TraceStatus.RUNNING,
        TraceStatus.FAILED,
    ]
    failed = sink.events[-1]
    assert failed.error_type == "RuntimeError"
    assert failed.error_message == "TradeFlow unavailable"
    assert failed.duration_ms == pytest.approx(125)


@pytest.mark.asyncio
async def test_trace_node_decorator_uses_owner_tracer() -> None:
    sink = RecordingTraceSink()

    class ExampleService:
        def __init__(self) -> None:
            self._tracer = Tracer(sink)

        @trace_node("example", "tests.example")
        async def execute(self, value: int) -> int:
            return value * 2

    result = await ExampleService().execute(4)

    assert result == 8
    assert [event.status for event in sink.events] == [
        TraceStatus.RUNNING,
        TraceStatus.PASSED,
    ]
