"""Application composition for technology-neutral tracing and exporters."""

from __future__ import annotations

import logging

from ntheemba.adapters.tracing import (
    CompositeTraceSink,
    InMemoryTraceSink,
    SafeStructuredLoggingTraceSink,
)
from ntheemba.config import Settings
from ntheemba.observability.runtime import ManagedTraceSink, ObservabilityRuntime
from ntheemba.observability.tracer import NullTraceSink
from ntheemba.ports.tracing import TraceSink


def build_runtime_trace_sink(
    settings: Settings,
    *,
    memory_sink: InMemoryTraceSink | None = None,
) -> tuple[TraceSink, ObservabilityRuntime]:
    """Build fail-open trace sinks for the configured environment."""

    runtime = ObservabilityRuntime(enabled=settings.tracing_enabled)
    if not settings.tracing_enabled:
        return NullTraceSink(), runtime

    sinks: list[TraceSink] = []
    if memory_sink is not None:
        sinks.append(ManagedTraceSink("memory", memory_sink, runtime))

    if settings.trace_export_enabled:
        exporter = SafeStructuredLoggingTraceSink(
            level=getattr(logging, settings.log_level),
            sample_rate=settings.trace_sample_rate,
            include_running=settings.trace_include_running,
            include_error_messages=settings.trace_include_error_messages,
            max_error_message_length=settings.trace_error_message_max_length,
        )
        sinks.append(ManagedTraceSink("structured_log", exporter, runtime))

    if not sinks:
        return NullTraceSink(), runtime
    if len(sinks) == 1:
        return sinks[0], runtime
    return CompositeTraceSink(sinks), runtime
