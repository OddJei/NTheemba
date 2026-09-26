"""Fail-open runtime health accounting for trace sink adapters."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Coroutine
from asyncio import Lock
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar

from ntheemba.observability.events import TraceEvent
from ntheemba.ports.tracing import TraceSink


T = TypeVar("T")


def configure_asyncio_runtime() -> None:
    """Configure asyncio for libraries that require selector loops on Windows."""

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def run_async(coroutine: Coroutine[object, object, T]) -> T:
    """Run one coroutine with Ntheemba's asyncio runtime settings."""

    configure_asyncio_runtime()
    return asyncio.run(coroutine)


@dataclass(frozen=True, slots=True)
class TraceSinkRuntimeSnapshot:
    """Safe operational counters for one configured trace sink."""

    name: str
    submitted_events: int
    emission_failures: int
    last_failure_at: datetime | None
    last_failure_type: str


@dataclass(frozen=True, slots=True)
class ObservabilityRuntimeSnapshot:
    """Aggregate observability runtime health."""

    status: str
    enabled: bool
    sink_count: int
    submitted_events: int
    emission_failures: int
    sinks: tuple[TraceSinkRuntimeSnapshot, ...]


@dataclass(slots=True)
class _MutableSinkCounters:
    submitted_events: int = 0
    emission_failures: int = 0
    last_failure_at: datetime | None = None
    last_failure_type: str = ""


class ObservabilityRuntime:
    """Track non-sensitive trace-export health without breaking workflows."""

    def __init__(self, *, enabled: bool) -> None:
        self._enabled = enabled
        self._counters: dict[str, _MutableSinkCounters] = {}
        self._lock = Lock()

    def register_sink(self, name: str) -> None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("sink name must not be empty")
        if cleaned in self._counters:
            raise ValueError(f"trace sink already registered: {cleaned}")
        self._counters[cleaned] = _MutableSinkCounters()

    async def record_success(self, name: str, event_count: int) -> None:
        if event_count < 0:
            raise ValueError("event_count must not be negative")
        async with self._lock:
            self._counters[name].submitted_events += event_count

    async def record_failure(self, name: str, error: Exception) -> None:
        async with self._lock:
            counters = self._counters[name]
            counters.emission_failures += 1
            counters.last_failure_at = datetime.now(UTC)
            counters.last_failure_type = type(error).__name__

    async def snapshot(self) -> ObservabilityRuntimeSnapshot:
        async with self._lock:
            sinks = tuple(
                TraceSinkRuntimeSnapshot(
                    name=name,
                    submitted_events=counters.submitted_events,
                    emission_failures=counters.emission_failures,
                    last_failure_at=counters.last_failure_at,
                    last_failure_type=counters.last_failure_type,
                )
                for name, counters in sorted(self._counters.items())
            )
        total_failures = sum(sink.emission_failures for sink in sinks)
        status = "disabled" if not self._enabled else "degraded" if total_failures else "ready"
        return ObservabilityRuntimeSnapshot(
            status=status,
            enabled=self._enabled,
            sink_count=len(sinks),
            submitted_events=sum(sink.submitted_events for sink in sinks),
            emission_failures=total_failures,
            sinks=sinks,
        )


class ManagedTraceSink:
    """Wrap a sink with fail-open behavior and operational counters."""

    def __init__(
        self,
        name: str,
        sink: TraceSink,
        runtime: ObservabilityRuntime,
    ) -> None:
        self._name = name
        self._sink = sink
        self._runtime = runtime
        self._runtime.register_sink(name)

    async def emit(self, event: TraceEvent) -> None:
        try:
            await self._sink.emit(event)
        except Exception as error:
            await self._runtime.record_failure(self._name, error)
            return
        await self._runtime.record_success(self._name, 1)

    async def emit_many(self, events: tuple[TraceEvent, ...]) -> None:
        if not events:
            return
        try:
            await self._sink.emit_many(events)
        except Exception as error:
            await self._runtime.record_failure(self._name, error)
            return
        await self._runtime.record_success(self._name, len(events))
