"""Built-in observability smoke test for deployments and CI."""

from __future__ import annotations

from dataclasses import dataclass

from ntheemba.adapters.tracing import InMemoryTraceSink
from ntheemba.observability.context import new_trace_context
from ntheemba.observability.tracer import Tracer
from ntheemba.observability.validation import TraceValidationReport, validate_trace


@dataclass(frozen=True, slots=True)
class ObservabilitySelfCheckResult:
    """Result of a synthetic nested-span trace self-check."""

    status: str
    event_count: int
    trace_id: str
    validation: TraceValidationReport


async def run_observability_self_check() -> ObservabilitySelfCheckResult:
    """Emit and validate a synthetic trace without external dependencies."""

    sink = InMemoryTraceSink(max_events=16)
    tracer = Tracer(sink)
    root_context = new_trace_context(
        request_id="observability-self-check",
        business_id="system",
        conversation_id="self-check",
        message_id="self-check",
    )

    async with tracer.span(
        "observability.self_check",
        "observability",
        root_context=root_context,
    ):
        async with tracer.span("observability.self_check.child", "observability"):
            pass

    events = await sink.snapshot()
    validation = validate_trace(events)
    return ObservabilitySelfCheckResult(
        status="passed" if validation.valid and validation.complete else "failed",
        event_count=len(events),
        trace_id=root_context.trace_id,
        validation=validation,
    )
