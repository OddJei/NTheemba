from datetime import UTC, datetime

import pytest

from ntheemba.adapters.businesses import (
    InMemoryBusinessRegistry,
    InMemoryUnsupportedDeclarationSink,
)
from ntheemba.application.capability_runtime import (
    BusinessContextResolver,
    ChannelContextResolver,
    UnknownBusinessChannelError,
)
from ntheemba.domain.business import (
    BusinessChannel,
    BusinessProfile,
    ChannelRole,
    ChannelScope,
    PlatformCapability,
    ResolvedPlatformContext,
)
from ntheemba.domain.capabilities import Capability, CapabilityCatalogue
from ntheemba.domain.gateway import InboundGatewayMessage


def _message(session: str, recipient: str) -> InboundGatewayMessage:
    return InboundGatewayMessage(
        request_id="REQ-1",
        message_id="MSG-1",
        channel_instance_id=session,
        provider="waha",
        recipient_phone=recipient,
        customer_phone="+260970001111",
        text="hello",
        received_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_platform_marketplace_resolves_without_business_context() -> None:
    business = BusinessProfile(
        "BUS-A", "Business A", "tradeflow_standard", frozenset({Capability.PRODUCT_CATALOGUE.value})
    )
    platform = BusinessChannel(
        "platform-internal",
        "waha",
        None,
        "+260970000099",
        scope=ChannelScope.PLATFORM,
        role=ChannelRole.MARKETPLACE,
        external_session_id="ntheemba-main",
    )
    registry = InMemoryBusinessRegistry(businesses=(business,), channels=(platform,))
    business_resolver = BusinessContextResolver(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        observations=InMemoryUnsupportedDeclarationSink(),
    )
    resolver = ChannelContextResolver(registry=registry, business_resolver=business_resolver)

    context = await resolver.resolve(_message("ntheemba-main", "+260970000099"))

    assert isinstance(context, ResolvedPlatformContext)
    assert context.capabilities == frozenset({PlatformCapability.MARKETPLACE})
    assert context.channel.business_id is None


@pytest.mark.asyncio
async def test_exact_identity_must_match_session_and_recipient() -> None:
    channel = BusinessChannel(
        "internal-a",
        "waha",
        "BUS-A",
        "+260970000001",
        external_session_id="business-a-session",
    )
    business = BusinessProfile(
        "BUS-A", "Business A", "tradeflow_standard", frozenset({Capability.PRODUCT_CATALOGUE.value})
    )
    registry = InMemoryBusinessRegistry(businesses=(business,), channels=(channel,))
    resolver = ChannelContextResolver(
        registry=registry,
        business_resolver=BusinessContextResolver(
            registry=registry,
            catalogue=CapabilityCatalogue.canonical(),
            observations=InMemoryUnsupportedDeclarationSink(),
        ),
    )

    with pytest.raises(UnknownBusinessChannelError):
        await resolver.resolve(_message("wrong-session", "+260970000001"))
    with pytest.raises(UnknownBusinessChannelError):
        await resolver.resolve(_message("business-a-session", "+260970000002"))
