"""Tests for trace-sink fan-out behavior."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from ntheemba.adapters.tracing import CompositeTraceSink, InMemoryTraceSink
from ntheemba.observability.events import TraceEvent, TraceStatus


class FailingTraceSink:
    async def emit(self, event: TraceEvent) -> None:
        raise RuntimeError("sink unavailable")

    async def emit_many(self, events: tuple[TraceEvent, ...]) -> None:
        raise RuntimeError("sink unavailable")


def _event(index: int = 1) -> TraceEvent:
    return TraceEvent(
        trace_id="TRACE-1",
        span_id=f"SPAN-{index}",
        node_id=f"node.{index}",
        component="tests",
        status=TraceStatus.PASSED,
        occurred_at=datetime(2026, 7, 21, 12, index, tzinfo=UTC),
        duration_ms=1.0,
    )


@pytest.mark.asyncio
async def test_composite_fans_out_to_all_sinks() -> None:
    first = InMemoryTraceSink()
    second = InMemoryTraceSink()
    composite = CompositeTraceSink((first, second))

    await composite.emit_many((_event(1), _event(2)))

    assert await first.snapshot() == await second.snapshot()


@pytest.mark.asyncio
async def test_composite_isolates_sink_failure_by_default() -> None:
    healthy = InMemoryTraceSink()
    errors: list[str] = []
    composite = CompositeTraceSink(
        (FailingTraceSink(), healthy),
        on_error=lambda _sink, error: errors.append(str(error)),
    )

    await composite.emit(_event())

    assert len(await healthy.snapshot()) == 1
    assert errors == ["sink unavailable"]


@pytest.mark.asyncio
async def test_composite_strict_mode_surfaces_failure() -> None:
    composite = CompositeTraceSink((FailingTraceSink(),), strict=True)

    with pytest.raises(RuntimeError, match="sink unavailable"):
        await composite.emit(_event())


def test_composite_requires_at_least_one_sink() -> None:
    with pytest.raises(ValueError, match="at least one"):
        CompositeTraceSink(())
