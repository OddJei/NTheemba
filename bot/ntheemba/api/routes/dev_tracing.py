"""Developer-only HTTP endpoints for inspecting in-memory traces."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict

from ntheemba.application.trace_query_service import TraceQueryService
from ntheemba.devtools.redaction import redact_mapping
from ntheemba.observability.events import TraceEvent

router = APIRouter(prefix="/dev", tags=["developer-tracing"], include_in_schema=False)


class TraceSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trace_id: str
    conversation_id: str
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    event_count: int
    failed: bool


class TraceEventResponse(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str
    node_id: str
    component: str
    status: str
    request_id: str
    business_id: str
    conversation_id: str
    message_id: str
    event_id: str
    occurred_at: datetime
    duration_ms: float | None
    error_type: str
    error_message: str
    attributes: dict[str, Any]

    @classmethod
    def from_event(cls, event: TraceEvent) -> TraceEventResponse:
        return cls(
            trace_id=event.trace_id,
            span_id=event.span_id,
            parent_span_id=event.parent_span_id,
            node_id=event.node_id,
            component=event.component,
            status=event.status.value,
            request_id=event.request_id,
            business_id=event.business_id,
            conversation_id=event.conversation_id,
            message_id=event.message_id,
            event_id=event.event_id,
            occurred_at=event.occurred_at,
            duration_ms=event.duration_ms,
            error_type=event.error_type,
            error_message=event.error_message,
            attributes=redact_mapping(event.attributes),
        )


class TraceHealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sink: str
    events: int
    traces: int
    max_events: int


def _service(request: Request) -> TraceQueryService:
    service = getattr(request.app.state, "trace_query_service", None)
    if not isinstance(service, TraceQueryService):
        raise HTTPException(status_code=503, detail="Trace query service unavailable")
    return service


@router.get("/traces", response_model=list[TraceSummaryResponse])
async def list_traces(request: Request) -> list[TraceSummaryResponse]:
    summaries = await _service(request).list_traces()
    return [TraceSummaryResponse.model_validate(summary) for summary in summaries]


@router.get("/traces/{trace_id}", response_model=list[TraceEventResponse])
async def get_trace(trace_id: str, request: Request) -> list[TraceEventResponse]:
    events = await _service(request).get_trace(trace_id)
    if not events:
        raise HTTPException(status_code=404, detail="Trace not found")
    return [TraceEventResponse.from_event(event) for event in events]


@router.get(
    "/conversations/{conversation_id}/traces",
    response_model=list[TraceSummaryResponse],
)
async def get_conversation_traces(
    conversation_id: str, request: Request
) -> list[TraceSummaryResponse]:
    summaries = await _service(request).get_conversation_traces(conversation_id)
    return [TraceSummaryResponse.model_validate(summary) for summary in summaries]


@router.delete("/traces", status_code=status.HTTP_204_NO_CONTENT)
async def clear_traces(request: Request) -> Response:
    await _service(request).clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/health/tracing", response_model=TraceHealthResponse)
async def tracing_health(request: Request) -> TraceHealthResponse:
    health = await _service(request).health()
    return TraceHealthResponse.model_validate(health)
