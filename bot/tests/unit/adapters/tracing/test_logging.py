"""Tests for structured trace logging."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from enum import StrEnum

import pytest
from ntheemba.adapters.tracing import LoggingTraceSink
from ntheemba.observability.events import TraceEvent, TraceStatus


class ExampleValue(StrEnum):
    READY = "ready"


def _event() -> TraceEvent:
    return TraceEvent(
        trace_id="TRACE-1",
        span_id="SPAN-1",
        node_id="workflow.execute",
        component="workflows.InformationWorkflow",
        status=TraceStatus.PASSED,
        request_id="REQ-1",
        business_id="BUS-1",
        conversation_id="CONV-1",
        message_id="MSG-1",
        occurred_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
        duration_ms=2.5,
        attributes={"intent": ExampleValue.READY, "sequence": (1, 2)},
    )


@pytest.mark.asyncio
async def test_logging_sink_emits_structured_json(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.trace")
    sink = LoggingTraceSink(logger)

    with caplog.at_level(logging.INFO, logger="tests.trace"):
        await sink.emit(_event())

    payload = json.loads(caplog.records[0].message)
    assert payload["trace_id"] == "TRACE-1"
    assert payload["status"] == "passed"
    assert payload["attributes"] == {"intent": "ready", "sequence": [1, 2]}
    assert payload["occurred_at"] == "2026-07-21T12:00:00+00:00"


@pytest.mark.asyncio
async def test_logging_sink_emits_batches_in_order(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.trace.batch")
    sink = LoggingTraceSink(logger)
    second = TraceEvent(
        trace_id="TRACE-1",
        span_id="SPAN-2",
        node_id="reply.publish",
        component="application.service",
        status=TraceStatus.RUNNING,
    )

    with caplog.at_level(logging.INFO, logger="tests.trace.batch"):
        await sink.emit_many((_event(), second))

    assert [json.loads(record.message)["node_id"] for record in caplog.records] == [
        "workflow.execute",
        "reply.publish",
    ]
