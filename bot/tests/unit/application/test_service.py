"""Tests for the complete Phase 3 message pipeline."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from ntheemba.application.service import (
    NtheembaService,
    ProcessingStatus,
    ProcessMessageCommand,
)
from ntheemba.application.session_coordinator import SessionCoordinator
from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowEvent,
    WorkflowReply,
    WorkflowResult,
    WorkflowRouter,
)
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.enums import Flow, IntentType, MessageRole, Stage
from ntheemba.domain.intents import Intent
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import TransitionPolicy
from ntheemba.ports.sessions import SessionKey
from tests.fakes.application import RecordingWorkflowHandler, StubInterpreter
from tests.fakes.audit import InMemoryAuditSink
from tests.fakes.publisher import InMemoryOutgoingPublisher
from tests.fakes.sessions import (
    InMemoryDeduplicationStore,
    InMemorySessionLockManager,
    InMemorySessionRepository,
)


def _intent(intent_type: IntentType = IntentType.BUSINESS_INFO) -> Intent:
    return Intent(
        type=intent_type,
        role=MessageRole.NEW_REQUEST,
        confidence=0.95,
    )


def _command(message_id: str = "MSG-1") -> ProcessMessageCommand:
    return ProcessMessageCommand(
        business_id="BUS-1",
        customer_id="260970000001",
        message_id=message_id,
        text="Where are you located?",
        whatsapp_session_id="WA-1",
        enabled_capabilities=frozenset({Capability.BUSINESS_INFORMATION}),
        received_at=datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
    )


class StubReplyLocalizer:
    def __init__(self, replies: tuple[WorkflowReply, ...]) -> None:
        self.replies = replies
        self.calls: list[tuple[WorkflowReply, ...]] = []

    async def localize_many(
        self,
        replies: tuple[WorkflowReply, ...],
    ) -> tuple[WorkflowReply, ...]:
        self.calls.append(replies)
        return self.replies


def _service(
    *,
    repository: InMemorySessionRepository,
    interpreter: StubInterpreter,
    handler: RecordingWorkflowHandler,
    publisher: InMemoryOutgoingPublisher | None = None,
    audit: InMemoryAuditSink | None = None,
) -> tuple[NtheembaService, InMemoryOutgoingPublisher, InMemoryAuditSink]:
    outgoing = publisher or InMemoryOutgoingPublisher()
    sink = audit or InMemoryAuditSink()
    coordinator = SessionCoordinator(
        repository,
        InMemorySessionLockManager(),
        clock=lambda: datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
    )
    service = NtheembaService(
        coordinator=coordinator,
        deduplication=InMemoryDeduplicationStore(
            clock=lambda: datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
        ),
        interpreter=interpreter,
        router=WorkflowRouter({IntentType.BUSINESS_INFO: handler}),
        publisher=outgoing,
        audit=sink,
        clock=lambda: datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
        request_id_factory=lambda: "REQ-1",
        deduplication_ttl=timedelta(days=1),
    )
    return service, outgoing, sink


@pytest.mark.asyncio
async def test_service_processes_saves_audits_and_publishes() -> None:
    repository = InMemorySessionRepository()
    policy = TransitionPolicy()

    def mutate(context: WorkflowContext) -> None:
        context.session.transition_to(
            policy,
            Flow.INFORMATION,
            Stage.INFORMATION_LOOKUP,
        )

    handler = RecordingWorkflowHandler(
        WorkflowResult(
            replies=(WorkflowReply.text_reply("We are in Mufulira."),),
            events=(WorkflowEvent("information.returned", {"source": "tradeflow"}),),
        ),
        mutation=mutate,
    )
    interpreter = StubInterpreter(_intent())
    service, publisher, audit = _service(
        repository=repository,
        interpreter=interpreter,
        handler=handler,
    )

    outcome = await service.process_message(_command())

    assert outcome.status == ProcessingStatus.PROCESSED
    assert len(outcome.published_message_ids) == 1
    assert publisher.messages[0].text == "We are in Mufulira."
    loaded = await repository.load(SessionKey("BUS-1", "260970000001"))
    assert loaded is not None
    assert loaded.revision == 1
    assert [turn.role for turn in loaded.recent_history] == ["customer", "assistant"]
    assert interpreter.calls[0][2] == frozenset({Capability.BUSINESS_INFORMATION})
    assert "message.processed" in {event.event_type for event in audit.events}
    assert "information.returned" in {event.event_type for event in audit.events}


@pytest.mark.asyncio
async def test_service_localizes_replies_before_history_and_publish() -> None:
    repository = InMemorySessionRepository()
    handler = RecordingWorkflowHandler(
        WorkflowResult(replies=(WorkflowReply.text_reply("We are in Mufulira."),))
    )
    localizer = StubReplyLocalizer(
        (
            WorkflowReply.text_reply(
                "Mwaiseni, we are in Mufulira.",
                metadata={"response_type": "business_information"},
            ),
        )
    )
    outgoing = InMemoryOutgoingPublisher()
    service = NtheembaService(
        coordinator=SessionCoordinator(repository, InMemorySessionLockManager()),
        deduplication=InMemoryDeduplicationStore(),
        interpreter=StubInterpreter(_intent()),
        router=WorkflowRouter({IntentType.BUSINESS_INFO: handler}),
        publisher=outgoing,
        audit=InMemoryAuditSink(),
        request_id_factory=lambda: "REQ-1",
        reply_localizer=localizer,
    )

    outcome = await service.process_message(_command())

    assert outcome.status == ProcessingStatus.PROCESSED
    assert localizer.calls[0][0].text == "We are in Mufulira."
    assert outgoing.messages[0].text == "Mwaiseni, we are in Mufulira."
    loaded = await repository.load(SessionKey("BUS-1", "260970000001"))
    assert loaded is not None
    assert loaded.recent_history[-1].text == "Mwaiseni, we are in Mufulira."


@pytest.mark.asyncio
async def test_duplicate_message_does_not_interpret_or_publish_twice() -> None:
    repository = InMemorySessionRepository()
    handler = RecordingWorkflowHandler(WorkflowResult(replies=(WorkflowReply.text_reply("Hello"),)))
    interpreter = StubInterpreter(_intent())
    outgoing = InMemoryOutgoingPublisher()
    audit = InMemoryAuditSink()
    coordinator = SessionCoordinator(repository, InMemorySessionLockManager())
    deduplication = InMemoryDeduplicationStore()
    service = NtheembaService(
        coordinator=coordinator,
        deduplication=deduplication,
        interpreter=interpreter,
        router=WorkflowRouter({IntentType.BUSINESS_INFO: handler}),
        publisher=outgoing,
        audit=audit,
        request_id_factory=lambda: "REQ-1",
    )

    first = await service.process_message(_command())
    second = await service.process_message(_command())

    assert first.status == ProcessingStatus.PROCESSED
    assert second.status == ProcessingStatus.DUPLICATE
    assert len(interpreter.calls) == 1
    assert len(outgoing.messages) == 1


@pytest.mark.asyncio
async def test_human_mode_records_message_and_suppresses_bot() -> None:
    repository = InMemorySessionRepository()
    policy = TransitionPolicy()
    session = Session.create(
        "BUS-1",
        "260970000001",
        now=datetime(2026, 7, 20, 11, 0, tzinfo=UTC),
    )
    session.transition_to(policy, Flow.ORDER, Stage.CATALOGUE_SEARCH)
    session.request_handover(policy)
    await repository.save(session, expected_revision=None)
    interpreter = StubInterpreter(_intent())
    handler = RecordingWorkflowHandler(WorkflowResult())
    service, publisher, _audit = _service(
        repository=repository,
        interpreter=interpreter,
        handler=handler,
    )

    outcome = await service.process_message(_command())

    assert outcome.status == ProcessingStatus.SUPPRESSED
    assert interpreter.calls == []
    assert publisher.messages == []
    loaded = await repository.load(SessionKey("BUS-1", "260970000001"))
    assert loaded is not None
    assert loaded.revision == 2
    assert loaded.recent_history[-1].text == "Where are you located?"


@pytest.mark.asyncio
async def test_workflow_failure_rolls_back_and_publishes_safe_fallback() -> None:
    repository = InMemorySessionRepository()
    policy = TransitionPolicy()

    def partial_mutation(context: WorkflowContext) -> None:
        context.session.transition_to(
            policy,
            Flow.INFORMATION,
            Stage.INFORMATION_LOOKUP,
        )

    handler = RecordingWorkflowHandler(
        RuntimeError("injected workflow failure"),
        mutation=partial_mutation,
    )
    service, publisher, audit = _service(
        repository=repository,
        interpreter=StubInterpreter(_intent()),
        handler=handler,
    )

    outcome = await service.process_message(_command())

    assert outcome.status == ProcessingStatus.FAILED
    assert outcome.error_code == "PROCESSING_FAILED"
    assert len(publisher.messages) == 1
    loaded = await repository.load(SessionKey("BUS-1", "260970000001"))
    assert loaded is not None
    assert loaded.flow == Flow.IDLE
    assert loaded.stage == Stage.START
    assert len(loaded.recent_history) == 2
    failure_events = [
        event for event in audit.events if event.event_type == "message.processing_failed"
    ]
    assert failure_events[0].data["error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_audit_failure_does_not_block_customer_reply() -> None:
    repository = InMemorySessionRepository()
    audit = InMemoryAuditSink()
    audit.fail_next = True
    handler = RecordingWorkflowHandler(WorkflowResult(replies=(WorkflowReply.text_reply("Hello"),)))
    service, publisher, _ = _service(
        repository=repository,
        interpreter=StubInterpreter(_intent()),
        handler=handler,
        audit=audit,
    )

    outcome = await service.process_message(_command())

    assert outcome.status == ProcessingStatus.PROCESSED
    assert publisher.messages[0].text == "Hello"


@pytest.mark.asyncio
async def test_audit_data_is_redacted_before_persistence() -> None:
    repository = InMemorySessionRepository()
    handler = RecordingWorkflowHandler(
        WorkflowResult(
            replies=(WorkflowReply.text_reply("Hello"),),
            events=(
                WorkflowEvent(
                    "test.private_event",
                    {
                        "candidate_count": 1,
                        "api_token": "secret-token",
                        "private_payload": {"supplier_cost": "12.00"},
                        "customer_phone": "+260970000001",
                        "sheet_id": "spreadsheet-private-id",
                    },
                ),
            ),
        )
    )
    service, _publisher, audit = _service(
        repository=repository,
        interpreter=StubInterpreter(_intent()),
        handler=handler,
    )

    outcome = await service.process_message(_command())

    assert outcome.status == ProcessingStatus.PROCESSED
    stored = next(event for event in audit.events if event.event_type == "test.private_event")
    assert stored.data == {
        "candidate_count": 1,
        "api_token": "[REDACTED]",
        "private_payload": "[REDACTED]",
        "customer_phone": "[REDACTED]",
        "sheet_id": "[REDACTED]",
    }


@pytest.mark.asyncio
async def test_dependency_failure_audit_is_redacted_and_duplicate_replay_is_suppressed() -> None:
    repository = InMemorySessionRepository()
    handler = RecordingWorkflowHandler(
        WorkflowResult(
            replies=(
                WorkflowReply.text_reply(
                    "The product system is temporarily unavailable. Please try again."
                ),
            ),
            events=(
                WorkflowEvent(
                    "catalogue.dependency_failed",
                    {
                        "dependency": "tradeflow",
                        "operation": "product search",
                        "retryable": True,
                        "safe_to_retry": True,
                        "api_token": "secret-token",
                        "private_payload": {"supplier_cost": "12.00"},
                    },
                ),
            ),
        )
    )
    service, publisher, audit = _service(
        repository=repository,
        interpreter=StubInterpreter(_intent()),
        handler=handler,
    )

    first = await service.process_message(_command("MSG-DEPENDENCY"))
    second = await service.process_message(_command("MSG-DEPENDENCY"))

    assert first.status == ProcessingStatus.PROCESSED
    assert second.status == ProcessingStatus.DUPLICATE
    assert len(handler.calls) == 1
    assert len(publisher.messages) == 1
    stored = next(
        event for event in audit.events if event.event_type == "catalogue.dependency_failed"
    )
    assert stored.request_id == "REQ-1"
    assert stored.data == {
        "dependency": "tradeflow",
        "operation": "product search",
        "retryable": True,
        "safe_to_retry": True,
        "api_token": "[REDACTED]",
        "private_payload": "[REDACTED]",
    }


@pytest.mark.asyncio
async def test_publisher_failure_releases_claim_for_retry() -> None:
    repository = InMemorySessionRepository()
    publisher = InMemoryOutgoingPublisher()
    publisher.fail_next = True
    handler = RecordingWorkflowHandler(WorkflowResult(replies=(WorkflowReply.text_reply("Hello"),)))
    interpreter = StubInterpreter(_intent())
    audit = InMemoryAuditSink()
    coordinator = SessionCoordinator(repository, InMemorySessionLockManager())
    deduplication = InMemoryDeduplicationStore()
    service = NtheembaService(
        coordinator=coordinator,
        deduplication=deduplication,
        interpreter=interpreter,
        router=WorkflowRouter({IntentType.BUSINESS_INFO: handler}),
        publisher=publisher,
        audit=audit,
        request_id_factory=lambda: "REQ-1",
    )

    first = await service.process_message(_command())
    second = await service.process_message(_command())

    assert first.status == ProcessingStatus.FAILED
    assert first.error_code == "INFRASTRUCTURE_FAILED"
    assert second.status == ProcessingStatus.PROCESSED
    assert len(publisher.messages) == 1
