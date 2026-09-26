from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest
from ntheemba.observability import TraceEvent, TraceStatus


def test_trace_event_is_immutable_and_copies_attributes() -> None:
    attributes = {"workflow": "order"}
    event = TraceEvent(
        trace_id="trace-1",
        span_id="span-1",
        node_id="interpret",
        component="application.interpretation",
        status=TraceStatus.PASSED,
        duration_ms=12.5,
        attributes=attributes,
    )

    attributes["workflow"] = "booking"

    assert event.attributes == {"workflow": "order"}
    with pytest.raises(TypeError):
        cast(Any, event.attributes)["workflow"] = "catalogue"


def test_failed_event_requires_error_type() -> None:
    with pytest.raises(ValueError, match="failed events must include error_type"):
        TraceEvent(
            trace_id="trace-1",
            span_id="span-1",
            node_id="publish",
            component="application.publisher",
            status=TraceStatus.FAILED,
        )


def test_running_event_rejects_duration() -> None:
    with pytest.raises(ValueError, match="running events"):
        TraceEvent(
            trace_id="trace-1",
            span_id="span-1",
            node_id="receive",
            component="application.service",
            status=TraceStatus.RUNNING,
            duration_ms=1,
        )


def test_event_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        TraceEvent(
            trace_id="trace-1",
            span_id="span-1",
            node_id="receive",
            component="application.service",
            status=TraceStatus.RUNNING,
            occurred_at=datetime(2026, 7, 21),
        )

    event = TraceEvent(
        trace_id="trace-1",
        span_id="span-1",
        node_id="receive",
        component="application.service",
        status=TraceStatus.RUNNING,
        occurred_at=datetime(2026, 7, 21, tzinfo=UTC),
    )
    assert event.occurred_at.tzinfo is UTC
