"""HTTP tests for the Phase 11.4 developer trace API."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ntheemba.adapters.tracing import InMemoryTraceSink
from ntheemba.observability.events import TraceEvent, TraceStatus


def event(
    *,
    trace_id: str = "trace-1",
    conversation_id: str = "conversation-1",
    offset_ms: int = 0,
    status: TraceStatus = TraceStatus.PASSED,
    attributes: Mapping[str, Any] | None = None,
) -> TraceEvent:
    return TraceEvent(
        trace_id=trace_id,
        span_id=f"span-{trace_id}-{offset_ms}",
        node_id="message.process",
        component="application",
        status=status,
        conversation_id=conversation_id,
        occurred_at=datetime(2026, 7, 21, tzinfo=UTC) + timedelta(milliseconds=offset_ms),
        duration_ms=1.0,
        error_type="RuntimeError" if status is TraceStatus.FAILED else "",
        error_message="failed" if status is TraceStatus.FAILED else "",
        attributes=attributes or {},
    )


@pytest.fixture
def trace_sink(app: FastAPI) -> InMemoryTraceSink:
    sink = app.state.trace_sink
    assert isinstance(sink, InMemoryTraceSink)
    return sink


def test_empty_trace_list(client: TestClient) -> None:
    response = client.get("/dev/traces")
    assert response.status_code == 200
    assert response.json() == []


def test_unknown_trace_returns_404(client: TestClient) -> None:
    response = client.get("/dev/traces/missing")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_lists_trace_summaries(client: TestClient, trace_sink: InMemoryTraceSink) -> None:
    await trace_sink.emit_many((event(offset_ms=0), event(offset_ms=25)))
    response = client.get("/dev/traces")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["trace_id"] == "trace-1"
    assert body[0]["event_count"] == 2
    assert body[0]["duration_ms"] == 25.0


@pytest.mark.asyncio
async def test_fetches_trace_events_in_order(
    client: TestClient, trace_sink: InMemoryTraceSink
) -> None:
    await trace_sink.emit_many((event(offset_ms=0), event(offset_ms=10)))
    response = client.get("/dev/traces/trace-1")
    assert response.status_code == 200
    assert [item["span_id"] for item in response.json()] == [
        "span-trace-1-0",
        "span-trace-1-10",
    ]


@pytest.mark.asyncio
async def test_filters_by_conversation(client: TestClient, trace_sink: InMemoryTraceSink) -> None:
    await trace_sink.emit_many(
        (
            event(trace_id="trace-a", conversation_id="wanted"),
            event(trace_id="trace-b", conversation_id="other"),
        )
    )
    response = client.get("/dev/conversations/wanted/traces")
    assert response.status_code == 200
    assert [item["trace_id"] for item in response.json()] == ["trace-a"]


@pytest.mark.asyncio
async def test_health_reports_store_counts(
    client: TestClient, trace_sink: InMemoryTraceSink
) -> None:
    await trace_sink.emit_many((event(trace_id="a"), event(trace_id="b")))
    response = client.get("/dev/health/tracing")
    assert response.status_code == 200
    assert response.json() == {
        "sink": "memory",
        "events": 2,
        "traces": 2,
        "max_events": 10000,
    }


@pytest.mark.asyncio
async def test_clear_traces(client: TestClient, trace_sink: InMemoryTraceSink) -> None:
    await trace_sink.emit(event())
    response = client.delete("/dev/traces")
    assert response.status_code == 204
    assert await trace_sink.snapshot() == ()


@pytest.mark.asyncio
async def test_trace_attributes_are_redacted_before_http_exposure(
    client: TestClient, trace_sink: InMemoryTraceSink
) -> None:
    await trace_sink.emit(
        event(
            attributes={
                "intent": "catalogue",
                "api_key": "never-expose-this",
                "nested": {"authorization": "Bearer secret"},
            }
        )
    )

    response = client.get("/dev/traces/trace-1")

    assert response.status_code == 200
    assert response.json()[0]["attributes"] == {
        "intent": "catalogue",
        "api_key": "[REDACTED]",
        "nested": {"authorization": "[REDACTED]"},
    }
