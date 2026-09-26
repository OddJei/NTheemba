"""Tests for human handover and trusted staff-control operations."""

from __future__ import annotations

import pytest
from ntheemba.application.workflow_router import WorkflowContext
from ntheemba.domain.enums import (
    ConversationMode,
    Flow,
    HandoverStatus,
    IntentType,
    MessageRole,
    SessionStatus,
    Stage,
)
from ntheemba.domain.intents import EntitySet, Intent, PendingQuestion
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import InvalidTransitionError, TransitionPolicy
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.handover import (
    HandoverWorkflow,
    HandoverWorkflowConfig,
    UnsupportedHandoverIntentError,
    build_handover_routes,
)


def _context(session: Session, intent_type: IntentType) -> WorkflowContext:
    return WorkflowContext(
        session=session,
        intent=Intent(
            type=intent_type,
            role=MessageRole.SYSTEM_COMMAND,
            confidence=1.0,
            entities=EntitySet(raw_text=intent_type.value),
        ),
        business_id=session.business_id,
        customer_id=session.customer_id,
        request_id="REQ-1",
        message_id="MSG-1",
    )


def _workflow(
    *,
    preserve_customer_workflow: bool = True,
) -> HandoverWorkflow:
    return HandoverWorkflow(
        responses=ResponseBuilder(),
        transition_policy=TransitionPolicy(),
        config=HandoverWorkflowConfig(preserve_customer_workflow=preserve_customer_workflow),
    )


@pytest.mark.asyncio
async def test_idle_handover_pauses_bot_without_suspended_workflow() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")

    result = await _workflow().handle(_context(session, IntentType.HANDOVER))

    assert session.flow == Flow.HANDOVER
    assert session.stage == Stage.WAITING_FOR_HUMAN
    assert session.mode == ConversationMode.HUMAN
    assert session.status == SessionStatus.PAUSED
    assert session.handover_status == HandoverStatus.WAITING
    assert session.suspended_state is None
    assert result.replies[0].metadata["response_type"] == "handover_requested"
    assert result.events[0].event_type == "handover.requested"


@pytest.mark.asyncio
async def test_order_handover_preserves_exact_state_and_pending_question() -> None:
    policy = TransitionPolicy()
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.transition_to(policy, Flow.ORDER, Stage.CATALOGUE_SEARCH)
    session.transition_to(policy, Flow.ORDER, Stage.PRODUCT_SELECTED)
    session.transition_to(policy, Flow.ORDER, Stage.QUANTITY)
    pending = PendingQuestion(
        prompt="How many would you like?",
        expected_intents=frozenset({IntentType.PROVIDE_QUANTITY}),
    )
    session.set_pending_question(pending)

    result = await _workflow().handle(_context(session, IntentType.HANDOVER))

    assert session.suspended_state is not None
    assert session.suspended_state.flow == Flow.ORDER
    assert session.suspended_state.stage == Stage.QUANTITY
    assert session.suspended_state.pending_question == pending
    assert session.pending_question is None
    assert result.events[0].data["workflow_preserved"] is True


@pytest.mark.asyncio
async def test_configuration_can_disable_workflow_preservation() -> None:
    policy = TransitionPolicy()
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.transition_to(policy, Flow.BOOKING, Stage.SERVICE_SELECTION)

    await _workflow(preserve_customer_workflow=False).handle(_context(session, IntentType.HANDOVER))

    assert session.suspended_state is None


def test_trusted_staff_takeover_marks_human_active() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    workflow = _workflow()
    policy = TransitionPolicy()
    session.request_handover(policy)

    result = workflow.activate_human(session)

    assert session.flow == Flow.HANDOVER
    assert session.stage == Stage.HUMAN_ACTIVE
    assert session.mode == ConversationMode.HUMAN
    assert session.status == SessionStatus.PAUSED
    assert session.handover_status == HandoverStatus.ACTIVE
    assert result.replies[0].metadata["response_type"] == "human_active"
    assert result.events[0].event_type == "handover.human_active"


def test_staff_takeover_requires_waiting_handover_state() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")

    with pytest.raises(InvalidTransitionError):
        _workflow().activate_human(session)


@pytest.mark.asyncio
async def test_resume_bot_restores_order_and_pending_question() -> None:
    policy = TransitionPolicy()
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.transition_to(policy, Flow.ORDER, Stage.CATALOGUE_SEARCH)
    session.transition_to(policy, Flow.ORDER, Stage.PRODUCT_SELECTED)
    session.transition_to(policy, Flow.ORDER, Stage.QUANTITY)
    pending = PendingQuestion(
        prompt="How many would you like?",
        expected_intents=frozenset({IntentType.PROVIDE_QUANTITY}),
    )
    session.set_pending_question(pending)
    session.request_handover(policy)
    session.mark_human_active(policy)

    result = await _workflow().handle(_context(session, IntentType.RESUME_BOT))

    assert session.flow == Flow.ORDER
    assert session.stage == Stage.QUANTITY
    assert session.mode == ConversationMode.BOT
    assert session.status == SessionStatus.ACTIVE
    assert session.handover_status == HandoverStatus.RESOLVED
    assert session.pending_question == pending
    assert session.suspended_state is None
    assert result.replies[0].text == ("Automated assistance has resumed. How many would you like?")
    assert result.events[0].data["restored_workflow"] is True


@pytest.mark.asyncio
async def test_resume_bot_without_preserved_workflow_returns_idle() -> None:
    policy = TransitionPolicy()
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.request_handover(policy)

    result = await _workflow().handle(_context(session, IntentType.RESUME_BOT))

    assert session.flow == Flow.IDLE
    assert session.stage == Stage.START
    assert session.mode == ConversationMode.BOT
    assert session.status == SessionStatus.ACTIVE
    assert result.events[0].data["restored_workflow"] is False


@pytest.mark.asyncio
async def test_close_session_clears_preserved_state_and_marks_resolved() -> None:
    policy = TransitionPolicy()
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.transition_to(policy, Flow.BOOKING, Stage.SERVICE_SELECTION)
    session.request_handover(policy)
    session.mark_human_active(policy)

    result = await _workflow().handle(_context(session, IntentType.CLOSE_SESSION))

    assert session.flow == Flow.IDLE
    assert session.stage == Stage.CLOSED
    assert session.status == SessionStatus.CLOSED
    assert session.handover_status == HandoverStatus.RESOLVED
    assert session.suspended_state is None
    assert result.replies[0].metadata["response_type"] == "conversation_closed"
    assert result.events[0].event_type == "handover.conversation_closed"


@pytest.mark.asyncio
async def test_unsupported_intent_is_rejected() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")

    with pytest.raises(UnsupportedHandoverIntentError):
        await _workflow().handle(_context(session, IntentType.START_ORDER))


def test_route_helper_registers_all_routed_handover_intents() -> None:
    workflow = _workflow()

    routes = build_handover_routes(workflow)

    assert set(routes) == {
        IntentType.HANDOVER,
        IntentType.RESUME_BOT,
        IntentType.CLOSE_SESSION,
    }
    assert all(handler is workflow for handler in routes.values())
