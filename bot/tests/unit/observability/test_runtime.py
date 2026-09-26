"""Tests for Phase 11.10 fail-open runtime accounting."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from ntheemba.observability.events import TraceEvent, TraceStatus
from ntheemba.observability.runtime import ManagedTraceSink, ObservabilityRuntime


@dataclass
class RecordingSink:
    events: list[TraceEvent] = field(default_factory=list)
    fail: bool = False

    async def emit(self, event: TraceEvent) -> None:
        if self.fail:
            raise RuntimeError("export unavailable")
        self.events.append(event)

    async def emit_many(self, events: tuple[TraceEvent, ...]) -> None:
        if self.fail:
            raise RuntimeError("export unavailable")
        self.events.extend(events)


def _event() -> TraceEvent:
    return TraceEvent(
        trace_id="trace-1",
        span_id="span-1",
        node_id="message.process",
        component="application",
        status=TraceStatus.RUNNING,
    )


@pytest.mark.asyncio
async def test_managed_sink_counts_successful_submissions() -> None:
    runtime = ObservabilityRuntime(enabled=True)
    delegate = RecordingSink()
    sink = ManagedTraceSink("recording", delegate, runtime)

    await sink.emit_many((_event(), _event()))
    snapshot = await runtime.snapshot()

    assert len(delegate.events) == 2
    assert snapshot.status == "ready"
    assert snapshot.submitted_events == 2
    assert snapshot.emission_failures == 0


@pytest.mark.asyncio
async def test_managed_sink_swallows_export_failure_and_marks_degraded() -> None:
    runtime = ObservabilityRuntime(enabled=True)
    sink = ManagedTraceSink("broken", RecordingSink(fail=True), runtime)

    await sink.emit(_event())
    snapshot = await runtime.snapshot()

    assert snapshot.status == "degraded"
    assert snapshot.submitted_events == 0
    assert snapshot.emission_failures == 1
    assert snapshot.sinks[0].last_failure_type == "RuntimeError"
