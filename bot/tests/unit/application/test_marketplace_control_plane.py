from __future__ import annotations

import pytest

from ntheemba.adapters.businesses import InMemoryBusinessRegistry
from ntheemba.adapters.marketplace import InMemoryMarketplaceRegistry
from ntheemba.application.marketplace import (
    MarketplaceConfigurationError,
    MarketplaceControlPlaneService,
)
from ntheemba.domain.business import BusinessProfile
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.marketplace import MarketplaceBusinessListing, MarketplaceListingStatus
from tests.fakes.audit import InMemoryAuditSink


@pytest.mark.asyncio
async def test_marketplace_listing_never_mutates_business_capabilities() -> None:
    business = BusinessProfile(
        "BUS-A",
        "Business A",
        "tradeflow_standard",
        frozenset({Capability.PRODUCT_CATALOGUE.value}),
    )
    businesses = InMemoryBusinessRegistry(businesses=(business,))
    marketplace = InMemoryMarketplaceRegistry()
    audit = InMemoryAuditSink()
    service = MarketplaceControlPlaneService(
        businesses=businesses,
        marketplace=marketplace,
        audit=audit,
    )

    listing = await service.set_listing(
        MarketplaceBusinessListing("BUS-A", MarketplaceListingStatus.ACTIVE, True),
        actor_id="operator:james",
        request_id="REQ-MP-1",
    )

    assert listing.eligible is True
    assert (await businesses.get_business("BUS-A")).declared_capabilities == frozenset(
        {Capability.PRODUCT_CATALOGUE.value}
    )
    assert audit.events[0].business_id == "__NTHEEMBA_PLATFORM__"
    assert audit.events[0].data["target_business_id"] == "BUS-A"


@pytest.mark.asyncio
async def test_disabled_business_cannot_be_made_discoverable() -> None:
    business = BusinessProfile(
        "BUS-A",
        "Business A",
        "tradeflow_standard",
        frozenset({Capability.PRODUCT_CATALOGUE.value}),
        enabled=False,
    )
    service = MarketplaceControlPlaneService(
        businesses=InMemoryBusinessRegistry(businesses=(business,)),
        marketplace=InMemoryMarketplaceRegistry(),
        audit=InMemoryAuditSink(),
    )

    with pytest.raises(MarketplaceConfigurationError, match="disabled businesses"):
        await service.set_listing(
            MarketplaceBusinessListing("BUS-A", MarketplaceListingStatus.ACTIVE, True),
            actor_id="operator:james",
            request_id="REQ-MP-2",
        )
