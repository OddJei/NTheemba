"""Tests for channel resolution and capability declaration validation."""

from datetime import UTC, datetime

import pytest
from ntheemba.adapters.businesses import (
    InMemoryBusinessRegistry,
    InMemoryUnsupportedDeclarationSink,
)
from ntheemba.application.capability_runtime import (
    BusinessContextResolver,
    CapabilityAwareWorkflowRouter,
    UnknownBusinessChannelError,
)
from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowReply,
    WorkflowResult,
    WorkflowRouter,
)
from ntheemba.domain.business import BusinessChannel, BusinessProfile
from ntheemba.domain.capabilities import Capability, CapabilityCatalogue
from ntheemba.domain.enums import IntentType, MessageRole
from ntheemba.domain.gateway import InboundGatewayMessage
from ntheemba.domain.intents import Intent
from ntheemba.domain.session import Session
from tests.fakes.application import RecordingWorkflowHandler


def _message(*, channel: str = "wa-business-1") -> InboundGatewayMessage:
    return InboundGatewayMessage(
        request_id="request-1",
        message_id="message-1",
        channel_instance_id=channel,
        provider="openwa",
        recipient_phone="+260970000001",
        customer_phone="+260970000111",
        text="Hello",
        received_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_resolver_keeps_known_capabilities_and_records_unknown_ones() -> None:
    profile = BusinessProfile(
        business_id="business-1",
        display_name="Business One",
        adapter_type="tradeflow_standard",
        declared_capabilities=frozenset(
            {Capability.PRODUCT_CATALOGUE.value, "tradeflow.magic_checkout"}
        ),
    )
    channel = BusinessChannel(
        "wa-business-1",
        "openwa",
        profile.business_id,
        "+260970000001",
    )
    registry = InMemoryBusinessRegistry(businesses=(profile,), channels=(channel,))
    observations = InMemoryUnsupportedDeclarationSink()
    resolver = BusinessContextResolver(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        observations=observations,
    )

    context = await resolver.resolve(_message())

    assert context.capabilities == frozenset({Capability.PRODUCT_CATALOGUE})
    assert context.rejected_declarations == frozenset({"tradeflow.magic_checkout"})
    recorded = await observations.list_observations()
    assert len(recorded) == 1
    assert recorded[0].value == "tradeflow.magic_checkout"


@pytest.mark.asyncio
async def test_resolver_rejects_unknown_receiving_channel() -> None:
    registry = InMemoryBusinessRegistry()
    resolver = BusinessContextResolver(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        observations=InMemoryUnsupportedDeclarationSink(),
    )

    with pytest.raises(UnknownBusinessChannelError):
        await resolver.resolve(_message(channel="missing"))


@pytest.mark.asyncio
async def test_capability_guard_denies_empty_capability_context_before_workflow() -> None:
    handler = RecordingWorkflowHandler(
        WorkflowResult(replies=(WorkflowReply.text_reply("booking called"),))
    )
    router = CapabilityAwareWorkflowRouter(
        WorkflowRouter({IntentType.START_BOOKING: handler})
    )
    session = Session.create("harvest", "customer-1")

    result = await router.route(
        WorkflowContext(
            session=session,
            intent=Intent(
                type=IntentType.START_BOOKING,
                role=MessageRole.NEW_REQUEST,
                confidence=0.95,
            ),
            business_id="harvest",
            customer_id="customer-1",
            request_id="request-1",
            message_id="message-1",
            capabilities=frozenset(),
        )
    )

    assert handler.calls == []
    assert result.events[0].event_type == "capability.denied"
    assert "appointment.create" in result.events[0].data["missing"]
