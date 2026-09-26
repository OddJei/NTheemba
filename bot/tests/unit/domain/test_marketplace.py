from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType

import pytest

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
from ntheemba.domain.marketplace import (
    MarketplaceBusinessHandoffContext,
    MarketplaceBusinessListing,
    MarketplaceHandoff,
    MarketplaceListingStatus,
)


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
        channel=channel,
        role=ChannelRole.MARKETPLACE,
        capabilities=frozenset({PlatformCapability.MARKETPLACE}),
    )


def test_discoverable_marketplace_listing_must_be_active() -> None:
    with pytest.raises(ValueError, match="only active Marketplace listings"):
        MarketplaceBusinessListing(
            "BUS-A",
            status=MarketplaceListingStatus.PENDING,
            discoverable=True,
        )


def test_marketplace_handoff_context_keeps_platform_source_separate_from_business() -> None:
    business = BusinessProfile(
        "BUS-A",
        "Business A",
        "tradeflow_standard",
        frozenset({Capability.PRODUCT_CATALOGUE.value}),
        runtime_revision=4,
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
    handoff = MarketplaceHandoff(
        search_id="SEARCH-1",
        result_id="SEARCH-1:1",
        source_channel_id="platform-marketplace",
        target_business_id="BUS-A",
        business_product_id="BP-A",
        ncpc_product_id="PRD-1",
        ncpc_variant_id="VAR-1",
        product_name="Blue Band 500g",
        selling_price_snapshot=Decimal("25.00"),
        currency="ZMW",
        integration_id="TF-A",
        business_runtime_revision=4,
        created_at=datetime.now(UTC),
    )

    context = MarketplaceBusinessHandoffContext(
        source_platform_context=_platform(),
        business=business,
        capabilities=frozenset({Capability.PRODUCT_CATALOGUE}),
        integrations=(integration,),
        handoff=handoff,
    )

    assert context.source_platform_context.channel.scope is ChannelScope.PLATFORM
    assert context.business.business_id == "BUS-A"
    assert context.supports(Capability.PRODUCT_CATALOGUE)
    assert context.integration_for(Capability.PRODUCT_CATALOGUE) == integration
    assert PlatformCapability.MARKETPLACE.value not in business.declared_capabilities
