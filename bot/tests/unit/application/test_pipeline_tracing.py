"""Phase 11.2 tests for real message-pipeline instrumentation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from ntheemba.application.service import NtheembaService, ProcessingStatus, ProcessMessageCommand
from ntheemba.application.session_coordinator import SessionCoordinator
from ntheemba.application.workflow_router import WorkflowReply, WorkflowResult, WorkflowRouter
from ntheemba.domain.enums import IntentType, MessageRole
from ntheemba.domain.intents import Intent
from ntheemba.observability.events import TraceStatus
from ntheemba.observability.tracer import Tracer
from tests.fakes.application import RecordingWorkflowHandler, StubInterpreter
from tests.fakes.audit import InMemoryAuditSink
from tests.fakes.publisher import InMemoryOutgoingPublisher
from tests.fakes.sessions import (
    InMemoryDeduplicationStore,
    InMemorySessionLockManager,
    InMemorySessionRepository,
)
from tests.fakes.tracing import InMemoryTraceSink


def _command(message_id: str = "MSG-TRACE-1") -> ProcessMessageCommand:
    return ProcessMessageCommand(
        business_id="BUS-1",
        customer_id="260970000001",
        message_id=message_id,
        text="Where are you located?",
        request_id="REQ-TRACE-1",
        received_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
    )


def _build_service(
    handler: RecordingWorkflowHandler,
    sink: InMemoryTraceSink,
    *,
    publisher: InMemoryOutgoingPublisher | None = None,
) -> NtheembaService:
    tracer = Tracer(sink)
    router = WorkflowRouter(
        {IntentType.BUSINESS_INFO: handler},
        tracer=tracer,
    )
    return NtheembaService(
        coordinator=SessionCoordinator(
            InMemorySessionRepository(),
            InMemorySessionLockManager(),
        ),
        deduplication=InMemoryDeduplicationStore(),
        interpreter=StubInterpreter(
            Intent(
                type=IntentType.BUSINESS_INFO,
                role=MessageRole.NEW_REQUEST,
                confidence=0.98,
            )
        ),
        router=router,
        publisher=publisher or InMemoryOutgoingPublisher(),
        audit=InMemoryAuditSink(),
        tracer=tracer,
        request_id_factory=lambda: "REQ-TRACE-1",
    )


@pytest.mark.asyncio
async def test_successful_message_emits_ordered_pipeline_spans() -> None:
    sink = InMemoryTraceSink()
    service = _build_service(
        RecordingWorkflowHandler(
            WorkflowResult(replies=(WorkflowReply.text_reply("We are in Mufulira."),))
        ),
        sink,
    )

    outcome = await service.process_message(_command())

    assert outcome.status is ProcessingStatus.PROCESSED
    running_nodes = [event.node_id for event in sink.events if event.status is TraceStatus.RUNNING]
    assert running_nodes == [
        "message.process",
        "message.deduplicate",
        "session.open",
        "message.interpret",
        "workflow.route",
        "transition.validate",
        "workflow.execute",
        "session.commit",
        "reply.publish",
    ]
    assert all(event.trace_id == sink.events[0].trace_id for event in sink.events)
    assert sink.events[0].request_id == "REQ-TRACE-1"
    assert sink.events[0].business_id == "BUS-1"
    assert sink.events[0].message_id == "MSG-TRACE-1"


@pytest.mark.asyncio
async def test_nested_pipeline_spans_have_parent_child_relationships() -> None:
    sink = InMemoryTraceSink()
    service = _build_service(
        RecordingWorkflowHandler(WorkflowResult()),
        sink,
    )

    await service.process_message(_command())

    running = {event.node_id: event for event in sink.events if event.status is TraceStatus.RUNNING}
    assert running["message.deduplicate"].parent_span_id == running["message.process"].span_id
    assert running["message.interpret"].parent_span_id == running["session.open"].span_id
    assert running["transition.validate"].parent_span_id == running["workflow.route"].span_id
    assert running["workflow.execute"].parent_span_id == running["workflow.route"].span_id


@pytest.mark.asyncio
async def test_workflow_failure_marks_execution_span_failed_and_preserves_fallback() -> None:
    sink = InMemoryTraceSink()
    service = _build_service(
        RecordingWorkflowHandler(RuntimeError("workflow exploded")),
        sink,
    )

    outcome = await service.process_message(_command())

    assert outcome.status is ProcessingStatus.FAILED
    failed = [event for event in sink.events if event.status is TraceStatus.FAILED]
    assert [event.node_id for event in failed] == ["workflow.execute", "workflow.route"]
    assert failed[0].error_type == "RuntimeError"
    assert any(
        event.node_id == "session.commit" and event.attributes.get("recovery") is True
        for event in sink.events
    )
    assert any(event.node_id == "reply.publish" for event in sink.events)


@pytest.mark.asyncio
async def test_publisher_failure_is_traced_and_claim_release_is_visible() -> None:
    sink = InMemoryTraceSink()
    publisher = InMemoryOutgoingPublisher()
    publisher.fail_next = True
    service = _build_service(
        RecordingWorkflowHandler(WorkflowResult(replies=(WorkflowReply.text_reply("Hello"),))),
        sink,
        publisher=publisher,
    )

    outcome = await service.process_message(_command())

    assert outcome.error_code == "INFRASTRUCTURE_FAILED"
    failed = [event for event in sink.events if event.status is TraceStatus.FAILED]
    assert [event.node_id for event in failed] == ["reply.publish", "session.open"]
    assert any(event.node_id == "message.release_claim" for event in sink.events)


@pytest.mark.asyncio
async def test_duplicate_stops_after_deduplication_span() -> None:
    sink = InMemoryTraceSink()
    service = _build_service(
        RecordingWorkflowHandler(WorkflowResult()),
        sink,
    )

    first = await service.process_message(_command())
    second = await service.process_message(_command())

    assert first.status is ProcessingStatus.PROCESSED
    assert second.status is ProcessingStatus.DUPLICATE
    trace_ids = []
    for event in sink.events:
        if event.trace_id not in trace_ids:
            trace_ids.append(event.trace_id)
    second_nodes = [
        event.node_id
        for event in sink.events
        if event.trace_id == trace_ids[1] and event.status is TraceStatus.RUNNING
    ]
    assert second_nodes == ["message.process", "message.deduplicate"]
