"""Developer-only observability validation and runtime diagnostics."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from ntheemba.application.trace_query_service import TraceQueryService
from ntheemba.observability.runtime import ObservabilityRuntime
from ntheemba.observability.self_check import run_observability_self_check

router = APIRouter(prefix="/dev", tags=["developer-observability"], include_in_schema=False)


class ValidationIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    severity: str
    message: str
    trace_id: str
    span_id: str
    event_id: str


class TraceValidationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trace_id: str
    valid: bool
    complete: bool
    event_count: int
    span_count: int
    root_span_count: int
    issues: tuple[ValidationIssueResponse, ...]


class SnapshotValidationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    valid: bool
    complete: bool
    trace_count: int
    event_count: int
    issue_count: int
    traces: tuple[TraceValidationResponse, ...]


class TraceSinkRuntimeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    submitted_events: int
    emission_failures: int
    last_failure_at: datetime | None
    last_failure_type: str


class ObservabilityRuntimeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    enabled: bool
    sink_count: int
    submitted_events: int
    emission_failures: int
    sinks: tuple[TraceSinkRuntimeResponse, ...]


class ObservabilitySelfCheckResponse(BaseModel):
    status: str
    event_count: int
    trace_id: str
    validation: TraceValidationResponse


def _query_service(request: Request) -> TraceQueryService:
    service = getattr(request.app.state, "trace_query_service", None)
    if not isinstance(service, TraceQueryService):
        raise HTTPException(status_code=503, detail="Trace query service unavailable")
    return service


def _runtime(request: Request) -> ObservabilityRuntime:
    runtime = getattr(request.app.state, "observability_runtime", None)
    if not isinstance(runtime, ObservabilityRuntime):
        raise HTTPException(status_code=503, detail="Observability runtime unavailable")
    return runtime


@router.get(
    "/observability/validation",
    response_model=SnapshotValidationResponse,
)
async def validate_retained_traces(request: Request) -> SnapshotValidationResponse:
    report = await _query_service(request).validate_all()
    return SnapshotValidationResponse.model_validate(report)


@router.get(
    "/traces/{trace_id}/validation",
    response_model=TraceValidationResponse,
)
async def validate_one_trace(trace_id: str, request: Request) -> TraceValidationResponse:
    report = await _query_service(request).validate_trace(trace_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return TraceValidationResponse.model_validate(report)


@router.get(
    "/observability/runtime",
    response_model=ObservabilityRuntimeResponse,
)
async def observability_runtime(request: Request) -> ObservabilityRuntimeResponse:
    snapshot = await _runtime(request).snapshot()
    return ObservabilityRuntimeResponse.model_validate(snapshot)


@router.post(
    "/observability/self-check",
    response_model=ObservabilitySelfCheckResponse,
)
async def observability_self_check() -> ObservabilitySelfCheckResponse:
    result = await run_observability_self_check()
    return ObservabilitySelfCheckResponse(
        status=result.status,
        event_count=result.event_count,
        trace_id=result.trace_id,
        validation=TraceValidationResponse.model_validate(result.validation),
    )
