"""Full application integration test for a booking conversation."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest
from ntheemba.application.service import NtheembaService, ProcessingStatus, ProcessMessageCommand
from ntheemba.application.session_coordinator import SessionCoordinator
from ntheemba.application.workflow_router import WorkflowRouter
from ntheemba.domain.booking_draft import AppointmentSlot, ServiceSelection
from ntheemba.domain.enums import Stage
from ntheemba.ports.sessions import SessionKey
from ntheemba.ports.tradeflow import StaffOption
from ntheemba.services.interpretation import HybridInterpreter
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.booking import BookingWorkflow, build_booking_routes
from tests.fakes.audit import InMemoryAuditSink
from tests.fakes.publisher import InMemoryOutgoingPublisher
from tests.fakes.sessions import (
    InMemoryDeduplicationStore,
    InMemorySessionLockManager,
    InMemorySessionRepository,
)
from tests.fakes.tradeflow import InMemoryTradeFlow

NOW = datetime(2026, 7, 21, 10, 0, tzinfo=UTC)
BOOKING_DATE = date(2026, 7, 25)


@pytest.mark.asyncio
async def test_six_message_booking_flow_submits_once() -> None:
    tradeflow = InMemoryTradeFlow()
    service = ServiceSelection(
        service_id="SVC-1",
        name="Knotless Braids",
        duration_minutes=180,
        price=Decimal("350"),
        currency="ZMW",
    )
    slot = AppointmentSlot(
        slot_id="SLOT-1",
        service_id="SVC-1",
        appointment_date=BOOKING_DATE,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    tradeflow.services["BUS-1"] = {service.service_id: service}
    tradeflow.slots[("BUS-1", service.service_id, BOOKING_DATE)] = (slot,)
    tradeflow.staff[("BUS-1", service.service_id, BOOKING_DATE, time(9, 0))] = (
        StaffOption("STAFF-1", "Mary"),
        StaffOption("STAFF-2", "Ruth"),
    )

    repository = InMemorySessionRepository()
    coordinator = SessionCoordinator(
        repository=repository,
        locks=InMemorySessionLockManager(),
        clock=lambda: NOW,
    )
    workflow = BookingWorkflow(
        tradeflow=tradeflow,
        responses=ResponseBuilder(),
        clock=lambda: NOW,
    )
    publisher = InMemoryOutgoingPublisher()
    service_app = NtheembaService(
        coordinator=coordinator,
        deduplication=InMemoryDeduplicationStore(clock=lambda: NOW),
        interpreter=HybridInterpreter(),
        router=WorkflowRouter(build_booking_routes(workflow)),
        publisher=publisher,
        audit=InMemoryAuditSink(),
        clock=lambda: NOW,
        request_id_factory=lambda: "REQ-1",
    )

    messages = (
        "book Knotless Braids",
        "2026-07-25",
        "1",
        "skip",
        "Mary Banda 0971111111",
        "confirm",
    )
    outcomes = []
    for index, text in enumerate(messages, start=1):
        outcomes.append(
            await service_app.process_message(
                ProcessMessageCommand(
                    business_id="BUS-1",
                    customer_id="CUSTOMER-1",
                    message_id=f"MSG-{index}",
                    text=text,
                    received_at=NOW,
                )
            )
        )

    saved = await repository.load(SessionKey("BUS-1", "CUSTOMER-1"))
    assert all(outcome.status == ProcessingStatus.PROCESSED for outcome in outcomes)
    assert saved is not None
    assert saved.stage == Stage.SUBMITTED
    assert saved.booking_draft is not None
    assert saved.booking_draft.submitted
    assert len(tradeflow.bookings) == 1
    assert any(
        "No payment has been taken" in (message.text or "") for message in publisher.messages
    )
