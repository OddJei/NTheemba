import pytest

from ntheemba.domain.business import (
    BusinessChannel,
    BusinessProfile,
    ChannelRole,
    ChannelScope,
    PlatformCapability,
)
from ntheemba.domain.capabilities import Capability


def test_business_cannot_declare_marketplace_capability() -> None:
    with pytest.raises(ValueError, match="platform capabilities cannot be assigned"):
        BusinessProfile(
            "BUS-A",
            "Business A",
            "tradeflow_standard",
            frozenset({Capability.PRODUCT_CATALOGUE.value, PlatformCapability.MARKETPLACE.value}),
        )


def test_business_channel_cannot_use_marketplace_role() -> None:
    with pytest.raises(ValueError, match="business channels cannot use platform roles"):
        BusinessChannel(
            "ch-a",
            "waha",
            "BUS-A",
            "+260970000001",
            role=ChannelRole.MARKETPLACE,
        )


def test_platform_marketplace_channel_has_no_business_and_exposes_platform_capability() -> None:
    channel = BusinessChannel(
        "ntheemba-primary",
        "waha",
        None,
        "+260970000099",
        scope=ChannelScope.PLATFORM,
        role=ChannelRole.MARKETPLACE,
        is_primary=True,
        external_session_id="ntheemba-main",
        recipient_identifier="+260970000099",
    )

    assert channel.business_id is None
    assert channel.exact_identity == ("waha", "ntheemba-main", "+260970000099")
    assert channel.platform_capabilities == frozenset({PlatformCapability.MARKETPLACE})


def test_platform_channel_requires_platform_role() -> None:
    with pytest.raises(ValueError, match="platform channels require a platform role"):
        BusinessChannel(
            "platform-general",
            "waha",
            None,
            "+260970000099",
            scope=ChannelScope.PLATFORM,
            role=ChannelRole.BUSINESS_PRIMARY,
        )


def test_marketplace_is_not_in_business_capability_catalogue() -> None:
    from ntheemba.domain.capabilities import CapabilityCatalogue

    catalogue = CapabilityCatalogue.canonical()
    assert catalogue.contains("marketplace") is False
    assert "marketplace" not in catalogue.known_ids()


@pytest.mark.parametrize("capability_id", ["marketplace", "platform.marketplace"])
def test_business_rejects_all_marketplace_capability_identifiers(capability_id: str) -> None:
    with pytest.raises(ValueError, match="platform capabilities cannot be assigned"):
        BusinessProfile(
            "BUS-X",
            "Business X",
            "tradeflow_standard",
            frozenset({Capability.PRODUCT_CATALOGUE.value, capability_id}),
        )
