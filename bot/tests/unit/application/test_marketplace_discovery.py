from __future__ import annotations

from decimal import Decimal

import pytest

from ntheemba.adapters.businesses import InMemoryBusinessRegistry
from ntheemba.adapters.marketplace import InMemoryMarketplaceRegistry
from ntheemba.application.marketplace import MarketplaceProductDiscoveryService
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
        channel=channel,
        role=ChannelRole.MARKETPLACE,
        capabilities=frozenset({PlatformCapability.MARKETPLACE}),
    )


def _business(business_id: str) -> BusinessProfile:
    return BusinessProfile(
        business_id,
        business_id,
        "tradeflow_standard",
        frozenset({Capability.PRODUCT_CATALOGUE.value}),
        runtime_revision=2,
    )


def _integration(business_id: str, integration_id: str) -> BusinessIntegration:
    return BusinessIntegration(
        integration_id,
        business_id,
        "tradeflow_standard",
        f"https://{business_id.lower()}.example/exec",
        provider="tradeflow_http",
        auth_reference=f"env:{business_id}",
        capabilities=frozenset({Capability.PRODUCT_CATALOGUE.value}),
    )


@pytest.mark.asyncio
async def test_marketplace_search_queries_only_eligible_businesses_and_trusted_products() -> None:
    a, b, c = _business("BUS-A"), _business("BUS-B"), _business("BUS-C")
    ia = _integration("BUS-A", "TF-A")
    ib = _integration("BUS-B", "TF-B")
    ic = _integration("BUS-C", "TF-C")
    businesses = InMemoryBusinessRegistry(
        businesses=(a, b, c),
        integrations=(ia, ib, ic),
    )
    marketplace = InMemoryMarketplaceRegistry(
        listings=(
            MarketplaceBusinessListing("BUS-A", MarketplaceListingStatus.ACTIVE, True),
            MarketplaceBusinessListing("BUS-B", MarketplaceListingStatus.ACTIVE, True),
            MarketplaceBusinessListing("BUS-C", MarketplaceListingStatus.PAUSED, False),
        )
    )
    ncpc = InMemoryNCPC((CanonicalProduct("PRD-1", "Blue Band 500g", variant_id="VAR-1"),))
    pa, pb, pc = InMemoryTradeFlow(), InMemoryTradeFlow(), InMemoryTradeFlow()
    pa.products["BUS-A"] = {
        "A1": BusinessProduct(
            "A1",
            "PRD-1",
            "Blue Band 500g",
            Decimal("25"),
            "ZMW",
            3,
            ncpc_variant_id="VAR-1",
            shop_id="shop-a",
        )
    }
    pb.products["BUS-B"] = {
        "B1": BusinessProduct(
            "B1",
            None,
            "Blue Band local",
            Decimal("20"),
            "ZMW",
            5,
            identity_status="awaiting_ncpc_review",
        ),
        "B2": BusinessProduct(
            "B2",
            "PRD-1",
            "Blue Band 500g",
            Decimal("24"),
            "ZMW",
            0,
            ncpc_variant_id="VAR-1",
        ),
    }
    pc.products["BUS-C"] = {
        "C1": BusinessProduct(
            "C1",
            "PRD-1",
            "Blue Band 500g",
            Decimal("19"),
            "ZMW",
            10,
            ncpc_variant_id="VAR-1",
        )
    }
    factory = StaticFactory({"TF-A": pa, "TF-B": pb, "TF-C": pc})
    service = MarketplaceProductDiscoveryService(
        businesses=businesses,
        marketplace=marketplace,
        ncpc=ncpc,
        tradeflow_factory=factory,
    )

    result = await service.search(_platform(), ProductQuery("Blue Band 500g"))

    assert [offer.business_id for offer in result.offers] == ["BUS-A"]
    assert result.offers[0].ncpc_variant_id == "VAR-1"
    assert result.offers[0].shop_id == "shop-a"
    assert set(factory.builds) == {"TF-A", "TF-B"}
    assert "TF-C" not in factory.builds
    assert all(call[0] != "search_business_products" for call in pa.calls + pb.calls + pc.calls)


@pytest.mark.asyncio
async def test_marketplace_ncpc_no_match_never_falls_back_across_business_catalogues() -> None:
    business = _business("BUS-A")
    integration = _integration("BUS-A", "TF-A")
    businesses = InMemoryBusinessRegistry(businesses=(business,), integrations=(integration,))
    marketplace = InMemoryMarketplaceRegistry(
        listings=(MarketplaceBusinessListing("BUS-A", MarketplaceListingStatus.ACTIVE, True),)
    )
    port = InMemoryTradeFlow()
    port.products["BUS-A"] = {
        "A1": BusinessProduct(
            "A1",
            None,
            "Local mystery item",
            Decimal("10"),
            "ZMW",
            3,
            identity_status="awaiting_ncpc_review",
        )
    }
    factory = StaticFactory({"TF-A": port})
    service = MarketplaceProductDiscoveryService(
        businesses=businesses,
        marketplace=marketplace,
        ncpc=InMemoryNCPC(),
        tradeflow_factory=factory,
    )

    result = await service.search(_platform(), ProductQuery("mystery item"))

    assert result.offers == ()
    assert factory.builds == []
    assert port.calls == []


@pytest.mark.asyncio
async def test_ambiguous_catalogue_integration_fails_closed_for_that_business() -> None:
    business = _business("BUS-A")
    i1 = _integration("BUS-A", "TF-A1")
    i2 = _integration("BUS-A", "TF-A2")
    businesses = InMemoryBusinessRegistry(businesses=(business,), integrations=(i1, i2))
    marketplace = InMemoryMarketplaceRegistry(
        listings=(MarketplaceBusinessListing("BUS-A", MarketplaceListingStatus.ACTIVE, True),)
    )
    factory = StaticFactory({"TF-A1": InMemoryTradeFlow(), "TF-A2": InMemoryTradeFlow()})
    service = MarketplaceProductDiscoveryService(
        businesses=businesses,
        marketplace=marketplace,
        ncpc=InMemoryNCPC((CanonicalProduct("PRD-1", "Test", variant_id="VAR-1"),)),
        tradeflow_factory=factory,
    )

    result = await service.search(_platform(), ProductQuery("Test"))

    assert result.offers == ()
    assert result.unavailable_business_ids == ("BUS-A",)
    assert factory.builds == []
