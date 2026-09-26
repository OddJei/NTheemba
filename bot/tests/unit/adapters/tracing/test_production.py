"""Tests for the Phase 11.9 production structured-log exporter."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import pytest
from ntheemba.adapters.tracing import SafeStructuredLoggingTraceSink
from ntheemba.observability.events import TraceEvent, TraceStatus


def _event(
    *,
    status: TraceStatus = TraceStatus.PASSED,
    trace_id: str = "trace-1",
) -> TraceEvent:
    return TraceEvent(
        trace_id=trace_id,
        span_id="span-1",
        node_id="message.process",
        component="application",
        status=status,
        occurred_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
        duration_ms=None if status is TraceStatus.RUNNING else 2.0,
        error_type="RuntimeError" if status is TraceStatus.FAILED else "",
        error_message="secret password=abc" if status is TraceStatus.FAILED else "",
        attributes={"api_key": "hidden", "safe": "value"},
    )


@pytest.mark.asyncio
async def test_exporter_redacts_attributes_and_omits_error_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.production.trace")
    sink = SafeStructuredLoggingTraceSink(logger)

    with caplog.at_level(logging.INFO, logger=logger.name):
        await sink.emit(_event(status=TraceStatus.FAILED))

    payload = json.loads(caplog.records[0].message)
    assert payload["schema"] == "ntheemba.trace.v1"
    assert payload["attributes"] == {"api_key": "[REDACTED]", "safe": "value"}
    assert payload["error_type"] == "RuntimeError"
    assert payload["error_message"] == ""
    assert "password=abc" not in caplog.records[0].message


@pytest.mark.asyncio
async def test_failed_events_bypass_zero_sampling(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.production.failed")
    sink = SafeStructuredLoggingTraceSink(logger, sample_rate=0.0)

    with caplog.at_level(logging.INFO, logger=logger.name):
        await sink.emit(_event(status=TraceStatus.PASSED))
        await sink.emit(_event(status=TraceStatus.FAILED))

    assert len(caplog.records) == 1
    assert json.loads(caplog.records[0].message)["status"] == "failed"


@pytest.mark.asyncio
async def test_running_events_can_be_suppressed(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.production.running")
    sink = SafeStructuredLoggingTraceSink(logger, include_running=False)

    with caplog.at_level(logging.INFO, logger=logger.name):
        await sink.emit(_event(status=TraceStatus.RUNNING))

    assert caplog.records == []
