"""Tests for the bounded in-memory trace sink."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from ntheemba.adapters.tracing import InMemoryTraceSink
from ntheemba.observability.events import TraceEvent, TraceStatus


def _event(index: int, *, trace_id: str = "TRACE-1", conversation_id: str = "CONV-1") -> TraceEvent:
    return TraceEvent(
        trace_id=trace_id,
        span_id=f"SPAN-{index}",
        node_id=f"node.{index}",
        component="tests",
        status=TraceStatus.PASSED,
        conversation_id=conversation_id,
        occurred_at=datetime(2026, 7, 21, 12, index, tzinfo=UTC),
        duration_ms=1.0,
    )


@pytest.mark.asyncio
async def test_in_memory_sink_preserves_order_and_returns_snapshot() -> None:
    sink = InMemoryTraceSink()

    await sink.emit_many((_event(1), _event(2)))
    await sink.emit(_event(3))

    assert [event.node_id for event in await sink.snapshot()] == ["node.1", "node.2", "node.3"]


@pytest.mark.asyncio
async def test_in_memory_sink_evicts_oldest_events_at_capacity() -> None:
    sink = InMemoryTraceSink(max_events=2)

    await sink.emit_many((_event(1), _event(2), _event(3)))

    assert [event.node_id for event in await sink.snapshot()] == ["node.2", "node.3"]


@pytest.mark.asyncio
async def test_in_memory_sink_filters_trace_and_conversation() -> None:
    sink = InMemoryTraceSink()
    await sink.emit_many(
        (
            _event(1),
            _event(2, trace_id="TRACE-2"),
            _event(3, conversation_id="CONV-2"),
        )
    )

    assert [event.node_id for event in await sink.events_for_trace("TRACE-1")] == [
        "node.1",
        "node.3",
    ]
    assert [event.node_id for event in await sink.events_for_conversation("CONV-1")] == [
        "node.1",
        "node.2",
    ]


@pytest.mark.asyncio
async def test_in_memory_sink_clear_removes_all_events() -> None:
    sink = InMemoryTraceSink()
    await sink.emit(_event(1))

    await sink.clear()

    assert await sink.snapshot() == ()


def test_in_memory_sink_rejects_invalid_capacity() -> None:
    with pytest.raises(ValueError, match="max_events"):
        InMemoryTraceSink(max_events=0)
