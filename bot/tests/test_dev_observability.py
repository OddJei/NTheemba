"""HTTP tests for Phases 11.8-11.10 observability completion."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ntheemba.adapters.tracing import InMemoryTraceSink
from ntheemba.config import Settings
from ntheemba.main import create_app
from ntheemba.observability.events import TraceEvent, TraceStatus
from ntheemba.observability.tracer import Tracer

_BASE = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


def _event(*, status: TraceStatus, offset_ms: int) -> TraceEvent:
    return TraceEvent(
        trace_id="trace-valid",
        span_id="span-root",
        node_id="message.process",
        component="application",
        status=status,
        occurred_at=_BASE + timedelta(milliseconds=offset_ms),
        duration_ms=None if status is TraceStatus.RUNNING else 3.0,
    )


@pytest.fixture
def trace_sink(app: FastAPI) -> InMemoryTraceSink:
    sink = app.state.trace_sink
    assert isinstance(sink, InMemoryTraceSink)
    return sink


def test_empty_snapshot_validation_is_healthy(client: TestClient) -> None:
    response = client.get("/dev/observability/validation")

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "complete": True,
        "trace_count": 0,
        "event_count": 0,
        "issue_count": 0,
        "traces": [],
    }


@pytest.mark.asyncio
async def test_trace_validation_endpoint(
    client: TestClient,
    trace_sink: InMemoryTraceSink,
) -> None:
    await trace_sink.emit_many(
        (
            _event(status=TraceStatus.RUNNING, offset_ms=0),
            _event(status=TraceStatus.PASSED, offset_ms=3),
        )
    )

    response = client.get("/dev/traces/trace-valid/validation")

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["complete"] is True
    assert body["issues"] == []


def test_missing_trace_validation_returns_404(client: TestClient) -> None:
    assert client.get("/dev/traces/missing/validation").status_code == 404


def test_runtime_endpoint_reports_configured_sinks(client: TestClient) -> None:
    response = client.get("/dev/observability/runtime")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["enabled"] is True
    assert {sink["name"] for sink in body["sinks"]} == {"memory", "structured_log"}


def test_self_check_endpoint_passes(client: TestClient) -> None:
    response = client.post("/dev/observability/self-check")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "passed"
    assert body["event_count"] == 4
    assert body["validation"]["valid"] is True


@pytest.mark.asyncio
async def test_application_tracer_writes_to_developer_memory_sink(app: FastAPI) -> None:
    tracer = app.state.tracer
    assert isinstance(tracer, Tracer)

    async with tracer.span("test.root", "tests"):
        pass

    sink = app.state.trace_sink
    events = await sink.snapshot()
    assert [event.status for event in events] == [TraceStatus.RUNNING, TraceStatus.PASSED]


def test_production_build_has_runtime_tracer_without_developer_routes() -> None:
    app = create_app(
        Settings(
            environment="production",
            docs_enabled=False,
            dev_tools_enabled=True,
        )
    )

    with TestClient(app) as client:
        assert client.get("/dev/observability/runtime").status_code == 404
        readiness = client.get("/ready")

    assert isinstance(app.state.tracer, Tracer)
    assert hasattr(app.state, "observability_runtime")
    assert not hasattr(app.state, "trace_sink")
    assert readiness.status_code == 200
    assert readiness.json()["checks"]["observability"]["status"] == "ready"
