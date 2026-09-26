"""Tests for the service booking workflow."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest
from ntheemba.application.workflow_router import WorkflowContext
from ntheemba.domain.booking_draft import AppointmentSlot, BookingDraft, ServiceSelection
from ntheemba.domain.enums import Flow, IntentType, MessageRole, Stage
from ntheemba.domain.intents import EntitySet, Intent
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import TransitionPolicy
from ntheemba.ports.tradeflow import StaffOption
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.booking import BookingStateError, BookingWorkflow, build_booking_routes
from tests.fakes.tradeflow import InMemoryTradeFlow

TODAY = datetime(2026, 7, 21, 10, 0, tzinfo=UTC)
BOOKING_DATE = date(2026, 7, 25)


def _service(price: Decimal = Decimal("350")) -> ServiceSelection:
    return ServiceSelection(
        service_id="SVC-1",
        name="Knotless Braids",
        duration_minutes=180,
        price=price,
        currency="ZMW",
    )


def _slot(slot_id: str = "SLOT-1", start: time = time(9, 0)) -> AppointmentSlot:
    return AppointmentSlot(
        slot_id=slot_id,
        service_id="SVC-1",
        appointment_date=BOOKING_DATE,
        start_time=start,
        end_time=time(start.hour + 3, start.minute),
    )


def _tradeflow() -> InMemoryTradeFlow:
    tradeflow = InMemoryTradeFlow()
    tradeflow.services["BUS-1"] = {"SVC-1": _service()}
    tradeflow.slots[("BUS-1", "SVC-1", BOOKING_DATE)] = (
        _slot(),
        _slot("SLOT-2", time(13, 0)),
    )
    tradeflow.staff[("BUS-1", "SVC-1", BOOKING_DATE, time(9, 0))] = (
        StaffOption("STAFF-1", "Mary"),
        StaffOption("STAFF-2", "Ruth"),
    )
    return tradeflow


def _workflow(tradeflow: InMemoryTradeFlow | None = None) -> BookingWorkflow:
    return BookingWorkflow(
        tradeflow=tradeflow or _tradeflow(),
        responses=ResponseBuilder(),
        transition_policy=TransitionPolicy(),
        clock=lambda: TODAY,
    )


def _context(
    session: Session,
    intent_type: IntentType,
    *,
    entities: EntitySet | None = None,
    message_id: str = "MSG-1",
) -> WorkflowContext:
    return WorkflowContext(
        session=session,
        intent=Intent(
            type=intent_type,
            role=MessageRole.PENDING_ANSWER,
            confidence=1.0,
            entities=entities or EntitySet(raw_text=intent_type.value),
        ),
        business_id=session.business_id,
        customer_id=session.customer_id,
        request_id="REQ-1",
        message_id=message_id,
    )


@pytest.mark.asyncio
async def test_start_with_exact_service_moves_to_date() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")

    result = await _workflow().handle(
        _context(
            session,
            IntentType.START_BOOKING,
            entities=EntitySet(query="book Knotless Braids", raw_text="book Knotless Braids"),
        )
    )

    assert session.flow == Flow.BOOKING
    assert session.stage == Stage.PREFERRED_DATE
    assert session.booking_draft is not None
    assert session.booking_draft.service == _service()
    assert result.replies[-1].metadata["field"] == "preferred_date"


@pytest.mark.asyncio
async def test_multiple_services_are_numbered_for_selection() -> None:
    tradeflow = _tradeflow()
    tradeflow.services["BUS-1"]["SVC-2"] = ServiceSelection(
        service_id="SVC-2",
        name="Knotless Braids Long",
        duration_minutes=240,
        price=Decimal("450"),
        currency="ZMW",
    )
    session = Session.create("BUS-1", "CUSTOMER-1")

    result = await _workflow(tradeflow).handle(
        _context(
            session,
            IntentType.START_BOOKING,
            entities=EntitySet(query="book knotless", raw_text="book knotless"),
        )
    )

    assert session.stage == Stage.SERVICE_SELECTION
    assert session.booking_draft is not None
    assert len(session.booking_draft.service_candidates) == 2
    assert result.replies[0].metadata["response_type"] == "service_results"


@pytest.mark.asyncio
async def test_past_date_is_rejected() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    await _workflow().handle(
        _context(
            session,
            IntentType.START_BOOKING,
            entities=EntitySet(query="Knotless Braids", raw_text="Knotless Braids"),
        )
    )

    result = await _workflow().handle(
        _context(
            session,
            IntentType.PROVIDE_DATE,
            entities=EntitySet(preferred_date=date(2026, 7, 20), raw_text="2026-07-20"),
        )
    )

    assert session.stage == Stage.PREFERRED_DATE
    assert result.events[0].event_type == "booking.past_date_rejected"


@pytest.mark.asyncio
async def test_date_presents_available_slots() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    workflow = _workflow()
    await workflow.handle(
        _context(
            session,
            IntentType.START_BOOKING,
            entities=EntitySet(query="Knotless Braids", raw_text="Knotless Braids"),
        )
    )

    result = await workflow.handle(
        _context(
            session,
            IntentType.PROVIDE_DATE,
            entities=EntitySet(preferred_date=BOOKING_DATE, raw_text="2026-07-25"),
        )
    )

    assert session.stage == Stage.TIME_SELECTION
    assert session.booking_draft is not None
    assert len(session.booking_draft.available_slots) == 2
    assert result.replies[0].metadata["response_type"] == "available_slots"


@pytest.mark.asyncio
async def test_time_selection_with_multiple_staff_allows_skip() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    workflow = _workflow()
    await workflow.handle(
        _context(session, IntentType.START_BOOKING, entities=EntitySet(query="Knotless Braids"))
    )
    await workflow.handle(
        _context(
            session,
            IntentType.PROVIDE_DATE,
            entities=EntitySet(preferred_date=BOOKING_DATE),
        )
    )

    result = await workflow.handle(
        _context(
            session,
            IntentType.SELECT_TIME,
            entities=EntitySet(selection=1, raw_text="1"),
        )
    )

    assert session.stage == Stage.STAFF_SELECTION
    assert session.pending_question is not None
    assert session.pending_question.metadata["allow_skip"] is True
    assert "SKIP" in (result.replies[0].text or "")


@pytest.mark.asyncio
async def test_skip_staff_moves_to_customer_details() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    workflow = _workflow()
    await workflow.handle(
        _context(session, IntentType.START_BOOKING, entities=EntitySet(query="Knotless Braids"))
    )
    await workflow.handle(
        _context(session, IntentType.PROVIDE_DATE, entities=EntitySet(preferred_date=BOOKING_DATE))
    )
    await workflow.handle(
        _context(session, IntentType.SELECT_TIME, entities=EntitySet(selection=1))
    )

    result = await workflow.handle(
        _context(
            session,
            IntentType.SELECT_STAFF,
            entities=EntitySet(extras={"skip_staff": True}, raw_text="skip"),
        )
    )

    assert session.stage == Stage.CUSTOMER_DETAILS
    assert session.booking_draft is not None
    assert session.booking_draft.preferred_staff_id is None
    assert result.replies[0].metadata["field"] == "customer_name"


@pytest.mark.asyncio
async def test_customer_details_produce_validated_review() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    workflow = _workflow()
    await workflow.handle(
        _context(session, IntentType.START_BOOKING, entities=EntitySet(query="Knotless Braids"))
    )
    await workflow.handle(
        _context(session, IntentType.PROVIDE_DATE, entities=EntitySet(preferred_date=BOOKING_DATE))
    )
    await workflow.handle(
        _context(session, IntentType.SELECT_TIME, entities=EntitySet(selection=1))
    )
    await workflow.handle(
        _context(session, IntentType.SELECT_STAFF, entities=EntitySet(extras={"skip_staff": True}))
    )

    result = await workflow.handle(
        _context(
            session,
            IntentType.PROVIDE_CUSTOMER_DETAILS,
            entities=EntitySet(customer_name="Mary Banda", contact_number="0971111111"),
        )
    )

    assert session.stage == Stage.BOOKING_REVIEW
    assert session.booking_draft is not None
    assert session.booking_draft.ready_for_submission
    assert result.replies[0].metadata["response_type"] == "booking_review"


@pytest.mark.asyncio
async def test_confirm_submits_once_and_replays_result() -> None:
    tradeflow = _tradeflow()
    workflow = _workflow(tradeflow)
    session = Session.create("BUS-1", "CUSTOMER-1")
    draft = BookingDraft()
    draft.select_service(_service())
    draft.set_preferred_date(BOOKING_DATE)
    draft.set_available_slots((_slot(),))
    draft.select_slot(_slot())
    draft.set_customer("Mary Banda", "0971111111")
    draft.apply_final_validation(slot_confirmed=True, validation_reference="slot:review")
    session.booking_draft = draft
    session.flow = Flow.BOOKING
    session.stage = Stage.BOOKING_REVIEW

    first = await workflow.handle(_context(session, IntentType.CONFIRM, message_id="MSG-C1"))
    second = await workflow.handle(_context(session, IntentType.CONFIRM, message_id="MSG-C2"))

    assert session.stage == Stage.SUBMITTED
    assert len(tradeflow.bookings) == 1
    assert first.replies[0].metadata["created"] is True
    assert second.replies[0].metadata["created"] is False


@pytest.mark.asyncio
async def test_slot_disappearing_returns_current_alternatives() -> None:
    tradeflow = _tradeflow()
    workflow = _workflow(tradeflow)
    session = Session.create("BUS-1", "CUSTOMER-1")
    draft = BookingDraft()
    draft.select_service(_service())
    draft.set_preferred_date(BOOKING_DATE)
    draft.set_available_slots((_slot(),))
    draft.select_slot(_slot())
    draft.set_customer("Mary Banda", "0971111111")
    draft.apply_final_validation(slot_confirmed=True, validation_reference="slot:review")
    session.booking_draft = draft
    session.flow = Flow.BOOKING
    session.stage = Stage.BOOKING_REVIEW
    tradeflow.slots[("BUS-1", "SVC-1", BOOKING_DATE)] = (_slot("SLOT-2", time(13, 0)),)

    result = await workflow.handle(_context(session, IntentType.CONFIRM))

    assert session.stage == Stage.TIME_SELECTION
    assert result.replies[0].metadata["response_type"] == "booking_slot_changed"
    assert not tradeflow.bookings


@pytest.mark.asyncio
async def test_changed_service_price_requires_fresh_confirmation() -> None:
    tradeflow = _tradeflow()
    workflow = _workflow(tradeflow)
    session = Session.create("BUS-1", "CUSTOMER-1")
    draft = BookingDraft()
    draft.select_service(_service())
    draft.set_preferred_date(BOOKING_DATE)
    draft.set_available_slots((_slot(),))
    draft.select_slot(_slot())
    draft.set_customer("Mary Banda", "0971111111")
    draft.apply_final_validation(slot_confirmed=True, validation_reference="slot:review")
    session.booking_draft = draft
    session.flow = Flow.BOOKING
    session.stage = Stage.BOOKING_REVIEW
    tradeflow.services["BUS-1"]["SVC-1"] = _service(Decimal("375"))

    result = await workflow.handle(_context(session, IntentType.CONFIRM))

    assert session.stage == Stage.BOOKING_REVIEW
    assert result.replies[0].metadata["response_type"] == "booking_price_changed"
    assert not tradeflow.bookings


@pytest.mark.asyncio
async def test_correct_date_clears_dependent_state() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    draft = BookingDraft()
    draft.select_service(_service())
    draft.set_preferred_date(BOOKING_DATE)
    draft.set_available_slots((_slot(),))
    draft.select_slot(_slot())
    draft.set_customer("Mary Banda", "0971111111")
    session.booking_draft = draft
    session.flow = Flow.BOOKING
    session.stage = Stage.BOOKING_REVIEW

    result = await _workflow().handle(
        _context(
            session,
            IntentType.CORRECT,
            entities=EntitySet(extras={"field": "preferred_date"}),
        )
    )

    assert session.stage == Stage.PREFERRED_DATE
    assert draft.preferred_date is None
    assert draft.selected_slot is None
    assert result.replies[0].metadata["field"] == "preferred_date"


@pytest.mark.asyncio
async def test_cancel_clears_booking_draft() -> None:
    policy = TransitionPolicy()
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.transition_to(policy, Flow.BOOKING, Stage.SERVICE_SELECTION)
    session.booking_draft = BookingDraft()

    result = await _workflow().handle(_context(session, IntentType.CANCEL))

    assert session.flow == Flow.IDLE
    assert session.stage == Stage.CANCELLED
    assert session.booking_draft is None
    assert result.replies[0].metadata["response_type"] == "cancelled"


def test_route_helper_registers_booking_intents() -> None:
    routes = build_booking_routes(_workflow())

    assert set(routes) == {
        IntentType.START_BOOKING,
        IntentType.SELECT_ITEM,
        IntentType.PROVIDE_DATE,
        IntentType.SELECT_TIME,
        IntentType.SELECT_STAFF,
        IntentType.PROVIDE_CUSTOMER_DETAILS,
        IntentType.CONFIRM,
        IntentType.CORRECT,
        IntentType.CANCEL,
    }


@pytest.mark.asyncio
async def test_time_selection_outside_list_is_rejected() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.flow = Flow.BOOKING
    session.stage = Stage.TIME_SELECTION
    draft = BookingDraft()
    draft.select_service(_service())
    draft.set_preferred_date(BOOKING_DATE)
    draft.set_available_slots((_slot(),))
    session.booking_draft = draft

    with pytest.raises(BookingStateError, match="outside"):
        await _workflow().handle(
            _context(session, IntentType.SELECT_TIME, entities=EntitySet(selection=3))
        )
