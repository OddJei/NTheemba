from __future__ import annotations

from decimal import Decimal

import pytest

from ntheemba.adapters.businesses import InMemoryBusinessRegistry
from ntheemba.adapters.marketplace import InMemoryMarketplaceRegistry
from ntheemba.application.marketplace import (
    MarketplaceHandoffConsumptionService,
    MarketplaceHandoffService,
    MarketplaceProductDiscoveryService,
)
from ntheemba.application.platform_workflow_runtime import (
    PlatformWorkflowAction,
    PlatformWorkflowRouter,
)
from ntheemba.domain.business import (
    BusinessChannel,
    BusinessIntegration,
    BusinessProfile,
    ChannelRole,
    ChannelScope,
    PlatformCapability,
    ResolvedPlatformContext,
)
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.marketplace import MarketplaceBusinessListing, MarketplaceListingStatus
from ntheemba.domain.platform_session import PlatformConversationSession, PlatformConversationStage
from ntheemba.ports.ncpc import CanonicalProduct
from ntheemba.ports.tradeflow import BusinessProduct
from tests.fakes.ncpc import InMemoryNCPC
from tests.fakes.tradeflow import InMemoryTradeFlow


class StaticFactory:
    def __init__(self, port: InMemoryTradeFlow) -> None:
        self.port = port

    def build(self, _integration):
        return self.port


def _platform() -> ResolvedPlatformContext:
    channel = BusinessChannel(
        "platform-marketplace",
        "waha",
        None,
        "+260970000099",
        scope=ChannelScope.PLATFORM,
        role=ChannelRole.MARKETPLACE,
    )
    return ResolvedPlatformContext(
        channel,
        ChannelRole.MARKETPLACE,
        frozenset({PlatformCapability.MARKETPLACE}),
    )


def _router() -> PlatformWorkflowRouter:
    business = BusinessProfile(
        "BUS-A",
        "Business A",
        "tradeflow_standard",
        frozenset(
            {
                Capability.PRODUCT_CATALOGUE.value,
                Capability.PRODUCT_ORDER.value,
            }
        ),
        runtime_revision=3,
    )
    integration = BusinessIntegration(
        "TF-A",
        "BUS-A",
        "tradeflow_standard",
        "https://a.example/exec",
        capabilities=frozenset(
            {
                Capability.PRODUCT_CATALOGUE.value,
                Capability.PRODUCT_ORDER.value,
            }
        ),
    )
    businesses = InMemoryBusinessRegistry(
        businesses=(business,),
        integrations=(integration,),
    )
    marketplace = InMemoryMarketplaceRegistry(
        listings=(
            MarketplaceBusinessListing(
                "BUS-A",
                MarketplaceListingStatus.ACTIVE,
                True,
            ),
        )
    )
    port = InMemoryTradeFlow()
    port.products["BUS-A"] = {
        "A1": BusinessProduct(
            "A1",
            "PRD-1",
            "Blue Band 500g",
            Decimal("25"),
            "ZMW",
            4,
            ncpc_variant_id="VAR-1",
            shop_id="SHOP-A",
        )
    }
    factory = StaticFactory(port)
    discovery = MarketplaceProductDiscoveryService(
        businesses=businesses,
        marketplace=marketplace,
        ncpc=InMemoryNCPC(
            (CanonicalProduct("PRD-1", "Blue Band 500g", variant_id="VAR-1"),)
        ),
        tradeflow_factory=factory,
    )
    handoff = MarketplaceHandoffService(
        businesses=businesses,
        marketplace=marketplace,
        tradeflow_factory=factory,
    )
    consumption = MarketplaceHandoffConsumptionService(
        businesses=businesses,
        marketplace=marketplace,
        tradeflow_factory=factory,
    )
    return PlatformWorkflowRouter(
        discovery=discovery,
        handoff=handoff,
        consumption=consumption,
    )


@pytest.mark.asyncio
async def test_platform_router_search_select_consume_without_fake_business_session() -> None:
    router = _router()
    platform = _platform()
    session = PlatformConversationSession.create(
        platform.channel.channel_instance_id,
        "CUSTOMER-1",
    )

    search = await router.route(platform, session, "Blue Band 500g")
    assert search.action is PlatformWorkflowAction.REPLIED
    assert session.stage is PlatformConversationStage.AWAITING_SELECTION
    assert session.search is not None
    assert "Business A" in (search.replies[0].text or "")

    selected = await router.route(platform, session, "1")
    assert selected.action is PlatformWorkflowAction.REPLIED
    assert session.stage is PlatformConversationStage.HANDOFF_READY
    assert session.target_business_id == "BUS-A"

    consumed = await router.route(platform, session, "continue")
    assert consumed.action is PlatformWorkflowAction.BUSINESS_ENTRY_READY
    assert consumed.business_context is not None
    assert consumed.business_context.business.business_id == "BUS-A"
    # Platform state is still platform-owned until the unified runtime activates a business session.
    assert session.stage is PlatformConversationStage.HANDOFF_READY


@pytest.mark.asyncio
async def test_platform_router_can_reset_search_without_leaking_selected_business() -> None:
    router = _router()
    platform = _platform()
    session = PlatformConversationSession.create(
        platform.channel.channel_instance_id,
        "CUSTOMER-1",
    )
    await router.route(platform, session, "Blue Band 500g")
    await router.route(platform, session, "1")

    result = await router.route(platform, session, "search again")

    assert result.action is PlatformWorkflowAction.REPLIED
    assert session.stage is PlatformConversationStage.IDLE
    assert session.handoff_id == ""
    assert session.target_business_id == ""


@pytest.mark.asyncio
async def test_business_active_platform_session_is_delegated_not_researched() -> None:
    router = _router()
    platform = _platform()
    session = PlatformConversationSession.create(
        platform.channel.channel_instance_id,
        "CUSTOMER-1",
    )
    await router.route(platform, session, "Blue Band 500g")
    await router.route(platform, session, "1")
    consumed = await router.route(platform, session, "continue")
    assert consumed.business_context is not None
    session.activate_business(
        business_id="BUS-A",
        conversation_id="MPORDER-1",
    )

    delegated = await router.route(platform, session, "2")

    assert delegated.action is PlatformWorkflowAction.BUSINESS_CONTINUE
    assert delegated.replies == ()


@pytest.mark.asyncio
async def test_non_marketplace_platform_role_replies_without_entering_business_runtime() -> None:
    router = _router()
    channel = BusinessChannel(
        "platform-support",
        "waha",
        None,
        "+260970000098",
        scope=ChannelScope.PLATFORM,
        role=ChannelRole.PLATFORM_SUPPORT,
    )
    context = ResolvedPlatformContext(
        channel,
        ChannelRole.PLATFORM_SUPPORT,
        frozenset(),
    )
    session = PlatformConversationSession.create("platform-support", "CUSTOMER-1")

    result = await router.route(context, session, "hello")

    assert result.action is PlatformWorkflowAction.REPLIED
    assert result.business_context is None
    assert session.stage is PlatformConversationStage.IDLE
    assert "does not have an active deterministic workflow" in (result.replies[0].text or "")
