"""Reference business/channel profiles used by development and local migration."""

from __future__ import annotations

from ntheemba.domain.business import BusinessChannel, BusinessIntegration, BusinessProfile
from ntheemba.domain.capabilities import Capability


def reference_businesses() -> tuple[BusinessProfile, ...]:
    standard = frozenset(
        {
            Capability.BUSINESS_INFORMATION.value,
            Capability.BUSINESS_HOURS.value,
            Capability.FAQ.value,
            Capability.PRODUCT_CATALOGUE.value,
            Capability.PRODUCT_ORDER.value,
            Capability.COLLECTION.value,
            Capability.DELIVERY.value,
            Capability.HANDOVER.value,
        }
    )
    serah = frozenset(
        {
            Capability.BUSINESS_INFORMATION.value,
            Capability.BUSINESS_HOURS.value,
            Capability.FAQ.value,
            Capability.CLIENT_IDENTIFY.value,
            Capability.CLIENT_CREATE.value,
            Capability.PRODUCT_CATALOGUE.value,
            Capability.PRODUCT_ORDER.value,
            Capability.COLLECTION.value,
            Capability.SERVICE_CATALOGUE.value,
            Capability.APPOINTMENT_CREATE.value,
            Capability.APPOINTMENT_RESCHEDULE.value,
            Capability.APPOINTMENT_CANCEL.value,
            Capability.LOYALTY_READ.value,
            Capability.HANDOVER.value,
        }
    )
    return (
        BusinessProfile(
            "harvest-big-shop",
            "Harvest Big Shop",
            "tradeflow_standard",
            standard,
            business_type="retail",
        ),
        BusinessProfile(
            "amac-enterprise",
            "AMAC Enterprise",
            "tradeflow_standard",
            standard.difference({Capability.DELIVERY.value}),
            business_type="retail",
        ),
        BusinessProfile(
            "serahs-glow-lounge",
            "Serah's Glow Lounge",
            "tradeflow_serahs",
            serah,
            business_type="beauty-salon-retail",
        ),
    )


def reference_channels() -> tuple[BusinessChannel, ...]:
    return (
        BusinessChannel(
            "sim-wa-harvest", "openwa-simulator", "harvest-big-shop", "+260970000001"
        ),
        BusinessChannel(
            "sim-wa-amac", "openwa-simulator", "amac-enterprise", "+260970000002"
        ),
        BusinessChannel(
            "sim-wa-serahs", "openwa-simulator", "serahs-glow-lounge", "+260976078440"
        ),
    )


def reference_integrations() -> tuple[BusinessIntegration, ...]:
    """Return non-secret development integration routing records."""

    return (
        BusinessIntegration(
            "harvest-tradeflow-standard",
            "harvest-big-shop",
            "tradeflow_standard",
            "https://tradeflow.local/harvest",
            capabilities=reference_businesses()[0].declared_capabilities,
            config={"contract": "tradeflow.ntheemba.v1"},
        ),
        BusinessIntegration(
            "amac-tradeflow-standard",
            "amac-enterprise",
            "tradeflow_standard",
            "https://tradeflow.local/amac",
            capabilities=reference_businesses()[1].declared_capabilities,
            config={"contract": "tradeflow.ntheemba.v1"},
        ),
        BusinessIntegration(
            "serahs-tradeflow-custom",
            "serahs-glow-lounge",
            "tradeflow_serahs",
            "https://tradeflow.local/serahs-glow",
            capabilities=reference_businesses()[2].declared_capabilities,
            config={"contract": "tradeflow.ntheemba.v1"},
        ),
    )
