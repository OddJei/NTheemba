"""Execution tracing primitives for Ntheemba."""

from ntheemba.observability.context import (
    TraceContext,
    bind_trace_context,
    current_trace_context,
    new_trace_context,
    reset_trace_context,
    set_trace_context,
)
from ntheemba.observability.decorator import trace_node
from ntheemba.observability.events import TraceEvent, TraceStatus
from ntheemba.observability.runtime import (
    ManagedTraceSink,
    ObservabilityRuntime,
    ObservabilityRuntimeSnapshot,
    TraceSinkRuntimeSnapshot,
)
from ntheemba.observability.tracer import NullTraceSink, Tracer
from ntheemba.observability.validation import (
    TraceSnapshotValidationReport,
    TraceValidationIssue,
    TraceValidationReport,
    ValidationSeverity,
    validate_trace,
    validate_trace_snapshot,
)

__all__ = [
    "ManagedTraceSink",
    "NullTraceSink",
    "ObservabilityRuntime",
    "ObservabilityRuntimeSnapshot",
    "TraceContext",
    "TraceEvent",
    "TraceSinkRuntimeSnapshot",
    "TraceSnapshotValidationReport",
    "TraceStatus",
    "TraceValidationIssue",
    "TraceValidationReport",
    "Tracer",
    "ValidationSeverity",
    "bind_trace_context",
    "current_trace_context",
    "new_trace_context",
    "reset_trace_context",
    "set_trace_context",
    "trace_node",
    "validate_trace",
    "validate_trace_snapshot",
]
