from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from ntheemba.adapters.tradeflow import DynamicTradeFlowPort
from ntheemba.application.capability_runtime import CapabilityAwareWorkflowRouter
from ntheemba.application.workflow_router import WorkflowContext, WorkflowRouter
from ntheemba.domain.booking_draft import ServiceSelection
from ntheemba.domain.business import (
    BusinessChannel,
    BusinessIntegration,
    BusinessProfile,
    ResolvedBusinessContext,
)
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.enums import Flow, IntentType, MessageRole, Stage
from ntheemba.domain.intents import EntitySet, Intent
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import InvalidTransitionError
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.booking import BookingWorkflow, build_booking_routes
from tests.fakes.tradeflow import InMemoryTradeFlow


def _serah_context() -> ResolvedBusinessContext:
    capabilities = frozenset(
        {
            Capability.SERVICE_CATALOGUE,
            Capability.APPOINTMENT_CREATE,
        }
    )
    return ResolvedBusinessContext(
        business=BusinessProfile(
            "serah",
            "Serah's Glow",
            "tradeflow_serahs",
            frozenset(capability.value for capability in capabilities),
            runtime_revision=1,
        ),
        channel=BusinessChannel("wa-serah", "openwa", "serah", "+260970000002"),
        capabilities=capabilities,
        integrations=(
            BusinessIntegration(
                "serah-tradeflow",
                "serah",
                "tradeflow_serahs",
                "https://tradeflow.local/serah",
                capabilities=frozenset(capability.value for capability in capabilities),
            ),
        ),
        runtime_revision=1,
    )


def _booking_context(
    *,
    business_id: str,
    adapter_type: str,
    capabilities: frozenset[Capability],
) -> ResolvedBusinessContext:
    return ResolvedBusinessContext(
        business=BusinessProfile(
            business_id,
            business_id.title(),
            adapter_type,
            frozenset(capability.value for capability in capabilities),
            runtime_revision=1,
        ),
        channel=BusinessChannel(f"wa-{business_id}", "openwa", business_id, "+260970000099"),
        capabilities=capabilities,
        integrations=(
            BusinessIntegration(
                f"{business_id}-tradeflow",
                business_id,
                adapter_type,
                f"https://tradeflow.local/{business_id}",
                capabilities=frozenset(capability.value for capability in capabilities),
            ),
        ),
        runtime_revision=1,
    )


@pytest.mark.asyncio
async def test_booking_workflow_uses_serah_configured_integration() -> None:
    standard = InMemoryTradeFlow()
    serah = InMemoryTradeFlow()
    serah.services["serah"] = {
        "svc-1": ServiceSelection(
            service_id="svc-1",
            name="Knotless Braids",
            duration_minutes=180,
            price=Decimal("350"),
            currency="ZMW",
        )
    }
    tradeflow = DynamicTradeFlowPort(
        {
            "tradeflow_standard": standard,
            "tradeflow_serahs": serah,
        }
    )
    workflow = BookingWorkflow(
        tradeflow=tradeflow,
        responses=ResponseBuilder(),
        clock=lambda: datetime(2026, 8, 22, 10, 0, tzinfo=UTC),
    )
    router = WorkflowRouter(build_booking_routes(workflow))
    session = Session.create("serah", "customer-1")

    await router.route(
        WorkflowContext(
            session=session,
            intent=Intent(
                type=IntentType.START_BOOKING,
                role=MessageRole.NEW_REQUEST,
                confidence=1.0,
                entities=EntitySet(query="braids", raw_text="book braids"),
            ),
            business_id="serah",
            customer_id="customer-1",
            request_id="request-1",
            message_id="message-1",
            capabilities=frozenset(
                {Capability.SERVICE_CATALOGUE, Capability.APPOINTMENT_CREATE}
            ),
            channel_instance_id="wa-serah",
            business_context=_serah_context(),
        )
    )

    assert standard.calls == []
    assert serah.calls == [("search_services", ("serah", "braids"))]


@pytest.mark.asyncio
async def test_invalid_booking_transition_is_denied_before_tradeflow_call() -> None:
    serah = InMemoryTradeFlow()
    tradeflow = DynamicTradeFlowPort({"tradeflow_serahs": serah})
    workflow = BookingWorkflow(
        tradeflow=tradeflow,
        responses=ResponseBuilder(),
        clock=lambda: datetime(2026, 8, 23, 10, 0, tzinfo=UTC),
    )
    router = WorkflowRouter(build_booking_routes(workflow))
    session = Session.create("serah", "customer-1")
    session.flow = Flow.BOOKING
    session.stage = Stage.PREFERRED_DATE

    with pytest.raises(InvalidTransitionError):
        await router.route(
            WorkflowContext(
                session=session,
                intent=Intent(
                    type=IntentType.START_BOOKING,
                    role=MessageRole.NEW_REQUEST,
                    confidence=1.0,
                    entities=EntitySet(query="braids", raw_text="book braids"),
                ),
                business_id="serah",
                customer_id="customer-1",
                request_id="request-invalid-transition",
                message_id="message-invalid-transition",
                capabilities=frozenset(
                    {Capability.SERVICE_CATALOGUE, Capability.APPOINTMENT_CREATE}
                ),
                channel_instance_id="wa-serah",
                business_context=_serah_context(),
            )
        )

    assert serah.calls == []


@pytest.mark.asyncio
async def test_same_booking_workflow_is_capability_driven_for_any_business() -> None:
    booking_caps = frozenset(
        {Capability.SERVICE_CATALOGUE, Capability.APPOINTMENT_CREATE}
    )
    tradeflow_backend = InMemoryTradeFlow()
    tradeflow_backend.services["serah"] = {
        "svc-1": ServiceSelection(
            service_id="svc-1",
            name="Braids",
            duration_minutes=120,
            price=Decimal("250"),
            currency="ZMW",
        )
    }
    tradeflow_backend.services["clinic"] = {
        "svc-2": ServiceSelection(
            service_id="svc-2",
            name="Consultation",
            duration_minutes=30,
            price=Decimal("100"),
            currency="ZMW",
        )
    }
    tradeflow = DynamicTradeFlowPort({"tradeflow_booking": tradeflow_backend})
    workflow = BookingWorkflow(
        tradeflow=tradeflow,
        responses=ResponseBuilder(),
        clock=lambda: datetime(2026, 8, 23, 10, 0, tzinfo=UTC),
    )
    router = CapabilityAwareWorkflowRouter(WorkflowRouter(build_booking_routes(workflow)))

    for business_id, query in (("serah", "braids"), ("clinic", "consultation")):
        session = Session.create(business_id, "customer-1")
        result = await router.route(
            WorkflowContext(
                session=session,
                intent=Intent(
                    type=IntentType.START_BOOKING,
                    role=MessageRole.NEW_REQUEST,
                    confidence=1.0,
                    entities=EntitySet(query=query, raw_text=f"book {query}"),
                ),
                business_id=business_id,
                customer_id="customer-1",
                request_id=f"request-{business_id}",
                message_id=f"message-{business_id}",
                capabilities=booking_caps,
                channel_instance_id=f"wa-{business_id}",
                business_context=_booking_context(
                    business_id=business_id,
                    adapter_type="tradeflow_booking",
                    capabilities=booking_caps,
                ),
            )
        )
        assert result.events[0].event_type == "booking.service_selected"

    harvest = Session.create("harvest", "customer-1")
    denied = await router.route(
        WorkflowContext(
            session=harvest,
            intent=Intent(
                type=IntentType.START_BOOKING,
                role=MessageRole.NEW_REQUEST,
                confidence=1.0,
                entities=EntitySet(query="braids", raw_text="book braids"),
            ),
            business_id="harvest",
            customer_id="customer-1",
            request_id="request-harvest",
            message_id="message-harvest",
            capabilities=frozenset({Capability.PRODUCT_CATALOGUE, Capability.PRODUCT_ORDER}),
            channel_instance_id="wa-harvest",
            business_context=_booking_context(
                business_id="harvest",
                adapter_type="tradeflow_booking",
                capabilities=frozenset(
                    {Capability.PRODUCT_CATALOGUE, Capability.PRODUCT_ORDER}
                ),
            ),
        )
    )

    assert denied.events[0].event_type == "capability.denied"
    assert ("search_services", ("harvest", "braids")) not in tradeflow_backend.calls
    assert tradeflow_backend.calls == [
        ("search_services", ("serah", "braids")),
        ("search_services", ("clinic", "consultation")),
    ]
