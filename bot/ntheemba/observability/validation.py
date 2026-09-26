"""Trace-integrity validation for developer and operational checks."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum

from ntheemba.observability.events import TraceEvent, TraceStatus


class ValidationSeverity(StrEnum):
    """Severity assigned to one trace-validation issue."""

    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TraceValidationIssue:
    """One deterministic trace-integrity finding."""

    code: str
    severity: ValidationSeverity
    message: str
    trace_id: str
    span_id: str = ""
    event_id: str = ""


@dataclass(frozen=True, slots=True)
class TraceValidationReport:
    """Validation result for one trace."""

    trace_id: str
    valid: bool
    complete: bool
    event_count: int
    span_count: int
    root_span_count: int
    issues: tuple[TraceValidationIssue, ...]


@dataclass(frozen=True, slots=True)
class TraceSnapshotValidationReport:
    """Aggregate validation result for a retained trace snapshot."""

    valid: bool
    complete: bool
    trace_count: int
    event_count: int
    issue_count: int
    traces: tuple[TraceValidationReport, ...]


_TERMINAL_STATUSES = frozenset({TraceStatus.PASSED, TraceStatus.FAILED, TraceStatus.SKIPPED})


def validate_trace(events: tuple[TraceEvent, ...]) -> TraceValidationReport:
    """Validate span lifecycle, parentage, correlation, and event uniqueness."""

    if not events:
        raise ValueError("at least one trace event is required")

    ordered = tuple(sorted(events, key=lambda event: (event.occurred_at, event.event_id)))
    trace_id = ordered[0].trace_id
    issues: list[TraceValidationIssue] = []

    mismatched_trace = next((event for event in ordered if event.trace_id != trace_id), None)
    if mismatched_trace is not None:
        issues.append(
            _issue(
                "TRACE_ID_MISMATCH",
                ValidationSeverity.ERROR,
                "All events in a trace report must share the same trace_id.",
                trace_id,
                event=mismatched_trace,
            )
        )

    seen_event_ids: set[str] = set()
    for event in ordered:
        if event.event_id in seen_event_ids:
            issues.append(
                _issue(
                    "DUPLICATE_EVENT_ID",
                    ValidationSeverity.ERROR,
                    "Trace event identifiers must be unique.",
                    trace_id,
                    event=event,
                )
            )
        seen_event_ids.add(event.event_id)

    spans: dict[str, list[TraceEvent]] = defaultdict(list)
    for event in ordered:
        spans[event.span_id].append(event)

    root_span_ids: set[str] = set()
    for span_id, span_events in spans.items():
        span_issues, is_root = _validate_span(trace_id, span_id, span_events, spans)
        issues.extend(span_issues)
        if is_root:
            root_span_ids.add(span_id)

    if len(root_span_ids) != 1:
        issues.append(
            TraceValidationIssue(
                code="ROOT_SPAN_COUNT_INVALID",
                severity=ValidationSeverity.ERROR,
                message="A trace must contain exactly one root span.",
                trace_id=trace_id,
            )
        )

    for field_name in ("request_id", "business_id", "conversation_id", "message_id"):
        populated = {getattr(event, field_name) for event in ordered if getattr(event, field_name)}
        if len(populated) > 1:
            issues.append(
                TraceValidationIssue(
                    code="CORRELATION_MISMATCH",
                    severity=ValidationSeverity.ERROR,
                    message=f"Trace events contain conflicting {field_name} values.",
                    trace_id=trace_id,
                )
            )

    sorted_issues = tuple(
        sorted(
            issues,
            key=lambda issue: (
                issue.severity.value,
                issue.code,
                issue.span_id,
                issue.event_id,
            ),
        )
    )
    valid = not any(issue.severity is ValidationSeverity.ERROR for issue in sorted_issues)
    complete = not any(issue.code == "SPAN_MISSING_TERMINAL" for issue in sorted_issues)
    return TraceValidationReport(
        trace_id=trace_id,
        valid=valid,
        complete=complete,
        event_count=len(ordered),
        span_count=len(spans),
        root_span_count=len(root_span_ids),
        issues=sorted_issues,
    )


def validate_trace_snapshot(
    events: tuple[TraceEvent, ...],
) -> TraceSnapshotValidationReport:
    """Validate every trace in a retained snapshot without mixing trace IDs."""

    grouped: dict[str, list[TraceEvent]] = defaultdict(list)
    for event in events:
        grouped[event.trace_id].append(event)

    reports = tuple(
        validate_trace(tuple(trace_events))
        for _, trace_events in sorted(grouped.items(), key=lambda item: item[0])
    )
    return TraceSnapshotValidationReport(
        valid=all(report.valid for report in reports),
        complete=all(report.complete for report in reports),
        trace_count=len(reports),
        event_count=len(events),
        issue_count=sum(len(report.issues) for report in reports),
        traces=reports,
    )


def _validate_span(
    trace_id: str,
    span_id: str,
    events: list[TraceEvent],
    all_spans: dict[str, list[TraceEvent]],
) -> tuple[list[TraceValidationIssue], bool]:
    ordered = sorted(events, key=lambda event: (event.occurred_at, event.event_id))
    issues: list[TraceValidationIssue] = []
    running = [event for event in ordered if event.status is TraceStatus.RUNNING]
    terminal = [event for event in ordered if event.status in _TERMINAL_STATUSES]

    if not running:
        issues.append(
            _issue(
                "SPAN_MISSING_RUNNING",
                ValidationSeverity.ERROR,
                "Each span must begin with one running event.",
                trace_id,
                span_id=span_id,
            )
        )
    elif len(running) > 1:
        issues.append(
            _issue(
                "SPAN_MULTIPLE_RUNNING",
                ValidationSeverity.ERROR,
                "Each span may contain only one running event.",
                trace_id,
                event=running[1],
            )
        )

    if not terminal:
        issues.append(
            _issue(
                "SPAN_MISSING_TERMINAL",
                ValidationSeverity.WARNING,
                "The span is still running or its terminal event was not retained.",
                trace_id,
                span_id=span_id,
            )
        )
    elif len(terminal) > 1:
        issues.append(
            _issue(
                "SPAN_MULTIPLE_TERMINAL",
                ValidationSeverity.ERROR,
                "Each span may contain only one terminal event.",
                trace_id,
                event=terminal[1],
            )
        )

    if running and terminal and terminal[0].occurred_at < running[0].occurred_at:
        issues.append(
            _issue(
                "TERMINAL_BEFORE_RUNNING",
                ValidationSeverity.ERROR,
                "A terminal event cannot occur before its running event.",
                trace_id,
                event=terminal[0],
            )
        )

    first = ordered[0]
    if any(
        event.node_id != first.node_id
        or event.component != first.component
        or event.parent_span_id != first.parent_span_id
        for event in ordered[1:]
    ):
        issues.append(
            _issue(
                "SPAN_METADATA_MISMATCH",
                ValidationSeverity.ERROR,
                "Events in one span must preserve node, component, and parent metadata.",
                trace_id,
                span_id=span_id,
            )
        )

    is_root = not first.parent_span_id
    if not is_root and first.parent_span_id not in all_spans:
        issues.append(
            _issue(
                "MISSING_PARENT_SPAN",
                ValidationSeverity.ERROR,
                "The span references a parent that is not present in the trace.",
                trace_id,
                span_id=span_id,
            )
        )

    return issues, is_root


def _issue(
    code: str,
    severity: ValidationSeverity,
    message: str,
    trace_id: str,
    *,
    span_id: str = "",
    event: TraceEvent | None = None,
) -> TraceValidationIssue:
    return TraceValidationIssue(
        code=code,
        severity=severity,
        message=message,
        trace_id=trace_id,
        span_id=event.span_id if event is not None else span_id,
        event_id=event.event_id if event is not None else "",
    )
