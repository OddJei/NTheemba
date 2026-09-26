"""Read-only application service for developer trace inspection."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from ntheemba.adapters.tracing.in_memory import InMemoryTraceSink
from ntheemba.observability.events import TraceEvent
from ntheemba.observability.validation import (
    TraceSnapshotValidationReport,
    TraceValidationReport,
    validate_trace,
    validate_trace_snapshot,
)


@dataclass(frozen=True, slots=True)
class TraceSummary:
    """Compact summary of one retained execution trace."""

    trace_id: str
    conversation_id: str
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    event_count: int
    failed: bool


@dataclass(frozen=True, slots=True)
class TraceHealth:
    """Current bounded in-memory trace-store statistics."""

    sink: str
    events: int
    traces: int
    max_events: int


class TraceQueryService:
    """Query and administer retained developer traces."""

    def __init__(self, sink: InMemoryTraceSink) -> None:
        self._sink = sink

    async def list_traces(self) -> tuple[TraceSummary, ...]:
        events = await self._sink.snapshot()
        grouped: dict[str, list[TraceEvent]] = defaultdict(list)
        for event in events:
            grouped[event.trace_id].append(event)

        summaries = [self._summarize(trace_events) for trace_events in grouped.values()]
        return tuple(sorted(summaries, key=lambda item: item.started_at, reverse=True))

    async def get_trace(self, trace_id: str) -> tuple[TraceEvent, ...]:
        events = await self._sink.events_for_trace(trace_id)
        return tuple(sorted(events, key=lambda event: event.occurred_at))

    async def get_conversation_traces(self, conversation_id: str) -> tuple[TraceSummary, ...]:
        events = await self._sink.events_for_conversation(conversation_id)
        grouped: dict[str, list[TraceEvent]] = defaultdict(list)
        for event in events:
            grouped[event.trace_id].append(event)
        summaries = [self._summarize(trace_events) for trace_events in grouped.values()]
        return tuple(sorted(summaries, key=lambda item: item.started_at, reverse=True))

    async def clear(self) -> None:
        await self._sink.clear()

    async def validate_trace(self, trace_id: str) -> TraceValidationReport | None:
        events = await self.get_trace(trace_id)
        if not events:
            return None
        return validate_trace(events)

    async def validate_all(self) -> TraceSnapshotValidationReport:
        events = await self._sink.snapshot()
        return validate_trace_snapshot(events)

    async def health(self) -> TraceHealth:
        events = await self._sink.snapshot()
        return TraceHealth(
            sink="memory",
            events=len(events),
            traces=len({event.trace_id for event in events}),
            max_events=self._sink.max_events,
        )

    @staticmethod
    def _summarize(events: list[TraceEvent]) -> TraceSummary:
        ordered = sorted(events, key=lambda event: event.occurred_at)
        started_at = ordered[0].occurred_at
        finished_at = ordered[-1].occurred_at
        duration_ms = max(0.0, (finished_at - started_at).total_seconds() * 1000)
        conversation_id = next(
            (event.conversation_id for event in ordered if event.conversation_id), ""
        )
        return TraceSummary(
            trace_id=ordered[0].trace_id,
            conversation_id=conversation_id,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            event_count=len(ordered),
            failed=any(event.status.value == "failed" for event in ordered),
        )
