"""Tests for Phase 11.8 trace-integrity validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ntheemba.observability.events import TraceEvent, TraceStatus
from ntheemba.observability.validation import validate_trace, validate_trace_snapshot

_BASE = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


def _event(
    *,
    span_id: str,
    status: TraceStatus,
    offset_ms: int,
    parent_span_id: str = "",
    trace_id: str = "trace-1",
    event_id: str | None = None,
) -> TraceEvent:
    return TraceEvent(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        node_id=f"node.{span_id}",
        component="tests",
        status=status,
        event_id=event_id or f"event-{trace_id}-{span_id}-{status.value}-{offset_ms}",
        occurred_at=_BASE + timedelta(milliseconds=offset_ms),
        duration_ms=None if status is TraceStatus.RUNNING else 1.0,
        error_type="RuntimeError" if status is TraceStatus.FAILED else "",
    )


def test_valid_nested_trace_is_complete() -> None:
    events = (
        _event(span_id="root", status=TraceStatus.RUNNING, offset_ms=0),
        _event(
            span_id="child",
            parent_span_id="root",
            status=TraceStatus.RUNNING,
            offset_ms=1,
        ),
        _event(
            span_id="child",
            parent_span_id="root",
            status=TraceStatus.PASSED,
            offset_ms=2,
        ),
        _event(span_id="root", status=TraceStatus.PASSED, offset_ms=3),
    )

    report = validate_trace(events)

    assert report.valid is True
    assert report.complete is True
    assert report.span_count == 2
    assert report.root_span_count == 1
    assert report.issues == ()


def test_running_trace_is_valid_but_incomplete() -> None:
    report = validate_trace((_event(span_id="root", status=TraceStatus.RUNNING, offset_ms=0),))

    assert report.valid is True
    assert report.complete is False
    assert [issue.code for issue in report.issues] == ["SPAN_MISSING_TERMINAL"]


def test_missing_parent_and_missing_running_are_errors() -> None:
    report = validate_trace(
        (
            _event(
                span_id="child",
                parent_span_id="missing",
                status=TraceStatus.PASSED,
                offset_ms=1,
            ),
        )
    )

    assert report.valid is False
    assert {issue.code for issue in report.issues} >= {
        "MISSING_PARENT_SPAN",
        "ROOT_SPAN_COUNT_INVALID",
        "SPAN_MISSING_RUNNING",
    }


def test_multiple_terminal_events_are_rejected() -> None:
    report = validate_trace(
        (
            _event(span_id="root", status=TraceStatus.RUNNING, offset_ms=0),
            _event(span_id="root", status=TraceStatus.PASSED, offset_ms=1),
            _event(span_id="root", status=TraceStatus.SKIPPED, offset_ms=2),
        )
    )

    assert report.valid is False
    assert any(issue.code == "SPAN_MULTIPLE_TERMINAL" for issue in report.issues)


def test_snapshot_validation_keeps_traces_separate() -> None:
    events = (
        _event(span_id="root-a", status=TraceStatus.RUNNING, offset_ms=0, trace_id="a"),
        _event(span_id="root-a", status=TraceStatus.PASSED, offset_ms=1, trace_id="a"),
        _event(span_id="root-b", status=TraceStatus.RUNNING, offset_ms=2, trace_id="b"),
    )

    report = validate_trace_snapshot(events)

    assert report.trace_count == 2
    assert report.event_count == 3
    assert report.valid is True
    assert report.complete is False
    assert report.issue_count == 1
