"""Tests for the information and FAQ workflow."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import pytest
from ntheemba.application.workflow_router import WorkflowContext
from ntheemba.domain.enums import Flow, IntentType, MessageRole, Stage
from ntheemba.domain.intents import EntitySet, Intent, PendingQuestion
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import TransitionPolicy
from ntheemba.ports.tradeflow import (
    BusinessHours,
    BusinessInformation,
    FAQAnswer,
)
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.information import (
    InformationWorkflow,
    UnsupportedInformationIntentError,
    build_information_routes,
)
from tests.fakes.tradeflow import InMemoryTradeFlow


def _context(
    session: Session,
    intent_type: IntentType,
    *,
    role: MessageRole = MessageRole.NEW_REQUEST,
    query: str | None = None,
) -> WorkflowContext:
    text = query or ""
    return WorkflowContext(
        session=session,
        intent=Intent(
            type=intent_type,
            role=role,
            confidence=0.99,
            entities=EntitySet(query=query, raw_text=text),
        ),
        business_id=session.business_id,
        customer_id=session.customer_id,
        request_id="REQ-1",
        message_id="MSG-1",
    )


def _workflow(
    tradeflow: InMemoryTradeFlow,
    *,
    now: datetime = datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
) -> InformationWorkflow:
    return InformationWorkflow(
        tradeflow=tradeflow,
        responses=ResponseBuilder(),
        transition_policy=TransitionPolicy(),
        clock=lambda: now,
    )


@pytest.mark.asyncio
async def test_business_information_returns_session_to_idle() -> None:
    tradeflow = InMemoryTradeFlow()
    tradeflow.businesses["BUS-1"] = BusinessInformation(
        business_id="BUS-1",
        name="Harvest Big Shop",
        description="Groceries and household products.",
        location="Mufulira",
        contact_phone="0970000000",
    )
    session = Session.create("BUS-1", "CUSTOMER-1")

    result = await _workflow(tradeflow).handle(_context(session, IntentType.BUSINESS_INFO))

    assert result.replies[0].text is not None
    assert "Harvest Big Shop" in result.replies[0].text
    assert session.flow == Flow.IDLE
    assert session.stage == Stage.START
    assert result.events[0].event_type == "information.business_profile_served"


@pytest.mark.asyncio
async def test_business_hours_uses_injected_clock() -> None:
    tradeflow = InMemoryTradeFlow()
    requested_at = datetime(2026, 7, 21, 10, 30, tzinfo=UTC)
    tradeflow.hours["BUS-1"] = BusinessHours(
        is_open=True,
        local_date=date(2026, 7, 21),
        opens_at=time(8, 0),
        closes_at=time(18, 0),
    )
    session = Session.create("BUS-1", "CUSTOMER-1")

    result = await _workflow(tradeflow, now=requested_at).handle(
        _context(session, IntentType.BUSINESS_HOURS)
    )

    assert result.replies[0].text == ("Yes, the business is open now and closes at 18:00.")
    assert ("get_business_hours", ("BUS-1", requested_at)) in tradeflow.calls


@pytest.mark.asyncio
async def test_faq_returns_highest_ranked_approved_answer() -> None:
    tradeflow = InMemoryTradeFlow()
    tradeflow.faqs["BUS-1"] = (
        FAQAnswer(
            faq_id="FAQ-LOW",
            question="Do you deliver?",
            answer="Delivery is available in selected areas.",
            score=0.60,
        ),
        FAQAnswer(
            faq_id="FAQ-HIGH",
            question="Do you deliver?",
            answer="Yes. Delivery depends on your location.",
            score=0.95,
        ),
    )
    session = Session.create("BUS-1", "CUSTOMER-1")

    result = await _workflow(tradeflow).handle(
        _context(
            session,
            IntentType.FAQ,
            query="Do you deliver?",
        )
    )

    assert result.replies[0].text == "Yes. Delivery depends on your location."
    assert result.events[0].event_type == "information.faq_answered"
    assert result.events[0].data["candidate_count"] == 2


@pytest.mark.asyncio
async def test_faq_not_found_uses_approved_fallback() -> None:
    tradeflow = InMemoryTradeFlow()
    session = Session.create("BUS-1", "CUSTOMER-1")

    result = await _workflow(tradeflow).handle(
        _context(
            session,
            IntentType.FAQ,
            query="Can I pay using sea shells?",
        )
    )

    assert result.replies[0].metadata["response_type"] == "faq_not_found"
    assert result.events[0].event_type == "information.faq_not_found"
    assert session.flow == Flow.IDLE


@pytest.mark.asyncio
async def test_safe_hours_interruption_restores_order_question() -> None:
    tradeflow = InMemoryTradeFlow()
    tradeflow.hours["BUS-1"] = BusinessHours(
        is_open=True,
        local_date=date(2026, 7, 21),
        opens_at=time(8, 0),
        closes_at=time(18, 0),
    )
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

    result = await _workflow(tradeflow).handle(
        _context(
            session,
            IntentType.BUSINESS_HOURS,
            role=MessageRole.SAFE_INTERRUPTION,
        )
    )

    assert session.flow == Flow.ORDER
    assert session.stage == Stage.QUANTITY
    assert session.pending_question == pending
    assert session.suspended_state is None
    assert len(result.replies) == 2
    assert result.replies[1].text == ("Back to your previous request: How many would you like?")
    assert result.events[-1].event_type == ("information.previous_workflow_resumed")


@pytest.mark.asyncio
async def test_dependency_failure_still_restores_interrupted_workflow() -> None:
    tradeflow = InMemoryTradeFlow()
    policy = TransitionPolicy()
    session = Session.create("BUS-404", "CUSTOMER-1")
    session.transition_to(policy, Flow.BOOKING, Stage.SERVICE_SELECTION)
    pending = PendingQuestion(
        prompt="Which service would you like to book?",
        expected_intents=frozenset({IntentType.SELECT_ITEM}),
    )
    session.set_pending_question(pending)

    result = await _workflow(tradeflow).handle(
        _context(
            session,
            IntentType.BUSINESS_INFO,
            role=MessageRole.SAFE_INTERRUPTION,
        )
    )

    assert session.flow == Flow.BOOKING
    assert session.stage == Stage.SERVICE_SELECTION
    assert session.pending_question == pending
    assert result.replies[0].metadata["response_type"] == "dependency_failure"
    assert result.replies[0].metadata["retryable"] is False
    assert result.replies[1].metadata["response_type"] == "workflow_resumed"
    assert result.events[0].data["error_type"] == "KeyError"


@pytest.mark.asyncio
async def test_missing_faq_query_asks_for_business_question_without_io() -> None:
    tradeflow = InMemoryTradeFlow()
    session = Session.create("BUS-1", "CUSTOMER-1")

    result = await _workflow(tradeflow).handle(_context(session, IntentType.FAQ))

    assert result.replies[0].metadata["response_type"] == "clarification"
    assert result.events[0].event_type == "information.faq_query_missing"
    assert not any(call[0] == "search_faqs" for call in tradeflow.calls)


@pytest.mark.asyncio
async def test_resolved_idle_state_is_normalized_before_information_request() -> None:
    tradeflow = InMemoryTradeFlow()
    tradeflow.businesses["BUS-1"] = BusinessInformation(
        business_id="BUS-1",
        name="Harvest Big Shop",
    )
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.flow = Flow.IDLE
    session.stage = Stage.RESOLVED

    await _workflow(tradeflow).handle(_context(session, IntentType.BUSINESS_INFO))

    assert session.flow == Flow.IDLE
    assert session.stage == Stage.START


@pytest.mark.asyncio
async def test_unsupported_intent_is_rejected() -> None:
    workflow = _workflow(InMemoryTradeFlow())
    session = Session.create("BUS-1", "CUSTOMER-1")

    with pytest.raises(UnsupportedInformationIntentError):
        await workflow.handle(_context(session, IntentType.START_ORDER))


def test_route_helper_registers_all_owned_intents() -> None:
    workflow = _workflow(InMemoryTradeFlow())

    routes = build_information_routes(workflow)

    assert set(routes) == {
        IntentType.BUSINESS_INFO,
        IntentType.BUSINESS_HOURS,
        IntentType.FAQ,
    }
    assert all(handler is workflow for handler in routes.values())
