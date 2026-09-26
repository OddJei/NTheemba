"""Tests for transition validation and workflow dispatch."""

from __future__ import annotations

import pytest
from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowNotRegisteredError,
    WorkflowReply,
    WorkflowResult,
    WorkflowRouter,
)
from ntheemba.domain.enums import Flow, IntentType, MessageRole, Stage
from ntheemba.domain.intents import Intent
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import InvalidTransitionError, TransitionPolicy
from tests.fakes.application import RecordingWorkflowHandler


def _context(session: Session, intent_type: IntentType) -> WorkflowContext:
    return WorkflowContext(
        session=session,
        intent=Intent(
            type=intent_type,
            role=MessageRole.NEW_REQUEST,
            confidence=0.9,
        ),
        business_id=session.business_id,
        customer_id=session.customer_id,
        request_id="REQ-1",
        message_id="MSG-1",
    )


@pytest.mark.asyncio
async def test_router_dispatches_approved_intent() -> None:
    handler = RecordingWorkflowHandler(
        WorkflowResult(replies=(WorkflowReply.text_reply("Business info"),))
    )
    router = WorkflowRouter({IntentType.BUSINESS_INFO: handler})
    session = Session.create("BUS-1", "CUSTOMER-1")

    result = await router.route(_context(session, IntentType.BUSINESS_INFO))

    assert result.replies[0].text == "Business info"
    assert len(handler.calls) == 1


@pytest.mark.asyncio
async def test_router_blocks_invalid_action_before_handler() -> None:
    policy = TransitionPolicy()
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.transition_to(policy, Flow.ORDER, Stage.CATALOGUE_SEARCH)
    session.transition_to(policy, Flow.ORDER, Stage.PRODUCT_SELECTED)
    session.transition_to(policy, Flow.ORDER, Stage.QUANTITY)
    handler = RecordingWorkflowHandler(WorkflowResult())
    router = WorkflowRouter({IntentType.SELECT_TIME: handler}, transition_policy=policy)

    with pytest.raises(InvalidTransitionError):
        await router.route(_context(session, IntentType.SELECT_TIME))

    assert handler.calls == []


@pytest.mark.asyncio
async def test_router_reports_unregistered_approved_intent() -> None:
    router = WorkflowRouter({})
    session = Session.create("BUS-1", "CUSTOMER-1")

    with pytest.raises(WorkflowNotRegisteredError):
        await router.route(_context(session, IntentType.BUSINESS_INFO))
