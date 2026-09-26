"""Application-level integration test for handover and bot suppression."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from ntheemba.application.service import (
    NtheembaService,
    ProcessingStatus,
    ProcessMessageCommand,
)
from ntheemba.application.session_coordinator import SessionCoordinator
from ntheemba.application.workflow_router import WorkflowRouter
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.enums import IntentType, MessageRole, Stage
from ntheemba.domain.intents import EntitySet, Intent
from ntheemba.ports.sessions import SessionKey
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.handover import HandoverWorkflow, build_handover_routes
from tests.fakes.audit import InMemoryAuditSink
from tests.fakes.publisher import InMemoryOutgoingPublisher
from tests.fakes.sessions import (
    InMemoryDeduplicationStore,
    InMemorySessionLockManager,
    InMemorySessionRepository,
)


class HandoverInterpreter:
    """Return handover for the first message and fail if called again."""

    def __init__(self) -> None:
        self.calls = 0

    async def interpret(
        self,
        text: str,
        session: object,
        *,
        capabilities: frozenset[Capability] = frozenset(),
    ) -> Intent:
        del capabilities
        self.calls += 1
        if self.calls > 1:
            raise AssertionError("interpreter must be suppressed in human mode")
        return Intent(
            type=IntentType.HANDOVER,
            role=MessageRole.GLOBAL_COMMAND,
            confidence=1.0,
            entities=EntitySet(raw_text=text),
        )


@pytest.mark.asyncio
async def test_handover_reply_then_next_customer_message_is_suppressed() -> None:
    repository = InMemorySessionRepository()
    locks = InMemorySessionLockManager()
    coordinator = SessionCoordinator(
        repository=repository,
        locks=locks,
        clock=lambda: datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
    )
    interpreter = HandoverInterpreter()
    workflow = HandoverWorkflow(responses=ResponseBuilder())
    router = WorkflowRouter(build_handover_routes(workflow))
    publisher = InMemoryOutgoingPublisher()
    service = NtheembaService(
        coordinator=coordinator,
        deduplication=InMemoryDeduplicationStore(
            clock=lambda: datetime(2026, 7, 21, 10, 0, tzinfo=UTC)
        ),
        interpreter=interpreter,
        router=router,
        publisher=publisher,
        audit=InMemoryAuditSink(),
        clock=lambda: datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
        request_id_factory=lambda: "REQ-1",
    )

    first = await service.process_message(
        ProcessMessageCommand(
            business_id="BUS-1",
            customer_id="CUSTOMER-1",
            message_id="MSG-1",
            text="I want to speak to a person",
            received_at=datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
        )
    )
    second = await service.process_message(
        ProcessMessageCommand(
            business_id="BUS-1",
            customer_id="CUSTOMER-1",
            message_id="MSG-2",
            text="Are you there?",
            received_at=datetime(2026, 7, 21, 10, 1, tzinfo=UTC),
        )
    )

    saved = await repository.load(SessionKey("BUS-1", "CUSTOMER-1"))
    assert first.status == ProcessingStatus.PROCESSED
    assert second.status == ProcessingStatus.SUPPRESSED
    assert interpreter.calls == 1
    assert len(publisher.messages) == 1
    assert saved is not None
    assert saved.stage == Stage.WAITING_FOR_HUMAN
    customer_turns = [turn.text for turn in saved.recent_history if turn.role == "customer"]
    assert customer_turns == [
        "I want to speak to a person",
        "Are you there?",
    ]
    assert any(
        turn.role == "assistant" and "paused automated replies" in turn.text
        for turn in saved.recent_history
    )
