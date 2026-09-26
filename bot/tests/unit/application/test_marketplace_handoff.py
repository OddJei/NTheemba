from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ntheemba.adapters.businesses import InMemoryBusinessRegistry
from ntheemba.adapters.marketplace import InMemoryMarketplaceRegistry
from ntheemba.application.marketplace import (
    MarketplaceAccessError,
    MarketplaceHandoffService,
    MarketplaceProductDiscoveryService,
    MarketplaceSelectionError,
)
from ntheemba.domain.business import (
    BusinessChannel,
    BusinessIntegration,
    BusinessProfile,
    ChannelRole,
    ChannelScope,
    PlatformCapability,
    ResolvedBusinessContext,
    ResolvedPlatformContext,
)
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.marketplace import MarketplaceBusinessListing, MarketplaceListingStatus
from ntheemba.domain.product_resolution import ProductQuery
from ntheemba.ports.ncpc import CanonicalProduct
from ntheemba.ports.tradeflow import BusinessProduct
from tests.fakes.ncpc import InMemoryNCPC
from tests.fakes.tradeflow import InMemoryTradeFlow


class StaticFactory:
    def __init__(self, ports):
        self.ports = ports
        self.builds: list[str] = []

    def build(self, integration):
        self.builds.append(integration.integration_id)
        return self.ports[integration.integration_id]


def _platform(channel_id: str = "platform-marketplace") -> ResolvedPlatformContext:
    channel = BusinessChannel(
        channel_id,
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


def _setup():
    business = BusinessProfile(
        "BUS-A",
        "Business A",
        "tradeflow_standard",
        frozenset({Capability.PRODUCT_CATALOGUE.value}),
        runtime_revision=7,
    )
    integration = BusinessIntegration(
        "TF-A",
        "BUS-A",
        "tradeflow_standard",
        "https://a.example/exec",
        provider="tradeflow_http",
        auth_reference="env:A",
        capabilities=frozenset({Capability.PRODUCT_CATALOGUE.value}),
    )
    businesses = InMemoryBusinessRegistry(businesses=(business,), integrations=(integration,))
    marketplace = InMemoryMarketplaceRegistry(
        listings=(MarketplaceBusinessListing("BUS-A", MarketplaceListingStatus.ACTIVE, True),)
    )
    ncpc = InMemoryNCPC((CanonicalProduct("PRD-1", "Blue Band 500g", variant_id="VAR-1"),))
    port = InMemoryTradeFlow()
    port.products["BUS-A"] = {
        "A1": BusinessProduct(
            "A1", "PRD-1", "Blue Band 500g", Decimal("25"), "ZMW", 3,
            ncpc_variant_id="VAR-1", shop_id="shop-a"
        )
    }
    factory = StaticFactory({"TF-A": port})
    discovery = MarketplaceProductDiscoveryService(
        businesses=businesses,
        marketplace=marketplace,
        ncpc=ncpc,
        tradeflow_factory=factory,
    )
    handoff = MarketplaceHandoffService(
        businesses=businesses,
        marketplace=marketplace,
        tradeflow_factory=factory,
    )
    return business, integration, businesses, marketplace, port, discovery, handoff


@pytest.mark.asyncio
async def test_selection_revalidates_price_and_shop_without_order() -> None:
    _business, _integration, _businesses, marketplace, port, discovery, handoff = _setup()
    platform = _platform()
    search = await discovery.search(platform, ProductQuery("Blue Band 500g"))
    assert search.offers[0].selling_price == Decimal("25")

    port.products["BUS-A"]["A1"] = BusinessProduct(
        "A1", "PRD-1", "Blue Band 500g", Decimal("27"), "ZMW", 2,
        ncpc_variant_id="VAR-1", shop_id="shop-a"
    )
    context = await handoff.select(platform, search, 1)

    assert context.business.business_id == "BUS-A"
    assert context.handoff.selling_price_snapshot == Decimal("27")
    assert context.handoff.shop_id == "shop-a"
    assert context.handoff.ncpc_product_id == "PRD-1"
    assert context.handoff.ncpc_variant_id == "VAR-1"
    assert await marketplace.get_handoff(context.handoff.handoff_id) == context.handoff
    assert [call[0] for call in port.calls].count("get_business_product") == 1
    assert all(call[0] != "create_order_request" for call in port.calls)


@pytest.mark.asyncio
async def test_selection_rejects_search_from_another_platform_channel() -> None:
    *_unused, discovery, handoff = _setup()
    search = await discovery.search(_platform("platform-a"), ProductQuery("Blue Band"))

    with pytest.raises(MarketplaceSelectionError, match="another platform channel"):
        await handoff.select(_platform("platform-b"), search, 1)


@pytest.mark.asyncio
async def test_selection_rejects_expired_search() -> None:
    *_unused, discovery, handoff = _setup()
    platform = _platform()
    search = await discovery.search(platform, ProductQuery("Blue Band"))

    with pytest.raises(MarketplaceSelectionError, match="expired"):
        await handoff.select(platform, search, 1, now=search.expires_at + timedelta(seconds=1))


@pytest.mark.asyncio
async def test_selection_rejects_business_that_was_paused_after_discovery() -> None:
    _business, _integration, _businesses, marketplace, _port, discovery, handoff = _setup()
    platform = _platform()
    search = await discovery.search(platform, ProductQuery("Blue Band"))
    await marketplace.save_listing(
        MarketplaceBusinessListing("BUS-A", MarketplaceListingStatus.PAUSED, False)
    )

    with pytest.raises(MarketplaceSelectionError, match="no longer Marketplace eligible"):
        await handoff.select(platform, search, 1)


@pytest.mark.asyncio
async def test_selection_rejects_product_that_loses_trusted_ncpc_state() -> None:
    _business, _integration, _businesses, _marketplace, port, discovery, handoff = _setup()
    platform = _platform()
    search = await discovery.search(platform, ProductQuery("Blue Band"))
    port.products["BUS-A"]["A1"] = BusinessProduct(
        "A1", None, "Blue Band 500g", Decimal("25"), "ZMW", 3,
        identity_status="awaiting_ncpc_review", shop_id="shop-a"
    )

    with pytest.raises(MarketplaceSelectionError, match="no longer Marketplace eligible"):
        await handoff.select(platform, search, 1)


@pytest.mark.asyncio
async def test_business_context_cannot_invoke_marketplace_handoff() -> None:
    business, integration, _businesses, _marketplace, _port, discovery, handoff = _setup()
    platform = _platform()
    search = await discovery.search(platform, ProductQuery("Blue Band"))
    business_channel = BusinessChannel("business-a", "waha", "BUS-A", "+260970000001")
    business_context = ResolvedBusinessContext(
        business=business,
        channel=business_channel,
        capabilities=frozenset({Capability.PRODUCT_CATALOGUE}),
        integrations=(integration,),
    )

    with pytest.raises(MarketplaceAccessError):
        await handoff.select(business_context, search, 1)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_repeated_selection_returns_same_handoff_without_revalidating_again() -> None:
    _business, _integration, _businesses, marketplace, port, discovery, handoff = _setup()
    platform = _platform()
    search = await discovery.search(platform, ProductQuery("Blue Band"))

    first = await handoff.select(platform, search, 1)
    calls_after_first = len(port.calls)
    second = await handoff.select(platform, search, 1)

    assert second.handoff.handoff_id == first.handoff.handoff_id
    saved = await marketplace.get_handoff_for_result(
        search.search_id,
        search.offers[0].result_id,
    )
    assert saved == first.handoff
    assert len(port.calls) == calls_after_first
