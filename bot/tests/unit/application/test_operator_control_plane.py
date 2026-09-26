from __future__ import annotations

from types import MappingProxyType

import pytest

from ntheemba.adapters.businesses import InMemoryBusinessRegistry, InMemoryRuntimeProfileCache
from ntheemba.application.operator_control_plane import (
    OperatorControlPlaneError,
    OperatorControlPlaneService,
)
from ntheemba.application.runtime_profiles import (
    RuntimeProfileCompiler,
    RuntimeProfileConfigurationService,
)
from ntheemba.domain.business import BusinessChannel, BusinessIntegration, BusinessProfile
from ntheemba.domain.capabilities import Capability, CapabilityCatalogue
from tests.fakes.audit import InMemoryAuditSink


BUSINESS = BusinessProfile(
    "BUS-A",
    "Business A",
    "tradeflow_standard",
    frozenset({Capability.PRODUCT_CATALOGUE.value}),
    runtime_revision=1,
)


def _service():
    registry = InMemoryBusinessRegistry(businesses=(BUSINESS,))
    cache = InMemoryRuntimeProfileCache()
    compiler = RuntimeProfileCompiler(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        cache=cache,
    )
    config = RuntimeProfileConfigurationService(registry=registry, compiler=compiler)
    audit = InMemoryAuditSink()
    service = OperatorControlPlaneService(
        registry=registry,
        configuration=config,
        audit=audit,
    )
    return service, registry, cache, audit


@pytest.mark.asyncio
async def test_operator_registers_channel_and_integration_with_audit() -> None:
    service, registry, _cache, audit = _service()
    channel = BusinessChannel("wa-a", "openwa", "BUS-A", "+260970000001")
    integration = BusinessIntegration(
        "tf-a",
        "BUS-A",
        "tradeflow_standard",
        "https://tradeflow-a.test/exec",
        provider="tradeflow_http",
        auth_reference="env:BUS_A_TOKEN",
        capabilities=frozenset({Capability.PRODUCT_CATALOGUE.value}),
        config=MappingProxyType({"timeout_seconds": 4}),
    )

    await service.register_channel(
        channel,
        actor_id="operator:james",
        request_id="REQ-CHAN",
    )
    await service.register_integration(
        integration,
        actor_id="operator:james",
        request_id="REQ-TF",
    )

    assert await registry.get_channel("wa-a") == channel
    assert (await registry.list_integrations("BUS-A"))[0] == integration
    completed = [event for event in audit.events if event.event_type.endswith("registered")]
    assert {event.event_type for event in completed} == {
        "control_plane.channel_registered",
        "control_plane.integration_registered",
    }
    integration_event = next(
        event for event in completed if event.event_type == "control_plane.integration_registered"
    )
    assert "base_url" not in integration_event.data
    assert "auth_reference" not in integration_event.data
    assert integration_event.data["auth_reference_configured"] is True


@pytest.mark.asyncio
async def test_operator_cannot_reassign_existing_channel_to_another_business() -> None:
    service, registry, _cache, audit = _service()
    other = BusinessProfile(
        "BUS-B",
        "Business B",
        "tradeflow_standard",
        frozenset({Capability.PRODUCT_CATALOGUE.value}),
    )
    await registry.register_business(other)
    await registry.register_channel(
        BusinessChannel("wa-shared", "openwa", "BUS-A", "+260970000001")
    )

    with pytest.raises(OperatorControlPlaneError, match="another business"):
        await service.register_channel(
            BusinessChannel("wa-shared", "openwa", "BUS-B", "+260970000002"),
            actor_id="operator:james",
            request_id="REQ-TAKEOVER",
        )

    assert (await registry.get_channel("wa-shared")).business_id == "BUS-A"
    assert not audit.events


@pytest.mark.asyncio
async def test_operator_capability_change_bumps_revision_and_invalidates_cache() -> None:
    service, registry, cache, audit = _service()
    await cache.set("BUS-A", "wa-a", 1, "cached", ttl_seconds=60)

    updated = await service.set_capability_enabled(
        "BUS-A",
        Capability.PRODUCT_ORDER.value,
        enabled=True,
        config={"collection_only": True},
        actor_id="operator:james",
        request_id="REQ-CAP",
    )

    assert updated.runtime_revision == 2
    assert Capability.PRODUCT_ORDER.value in updated.declared_capabilities
    assert dict(updated.capability_config[Capability.PRODUCT_ORDER.value]) == {
        "collection_only": True
    }
    assert await cache.get("BUS-A", "wa-a", 1) is None
    assert any(event.event_type == "control_plane.capability_changed" for event in audit.events)


@pytest.mark.asyncio
async def test_operator_integration_rotation_does_not_audit_endpoint_or_secret_reference() -> None:
    service, registry, _cache, audit = _service()
    await registry.register_integration(
        BusinessIntegration(
            "tf-a",
            "BUS-A",
            "tradeflow_standard",
            "https://old.test/exec",
            provider="tradeflow_http",
            auth_reference="env:OLD",
            capabilities=frozenset({Capability.PRODUCT_CATALOGUE.value}),
        )
    )

    updated = await service.update_integration(
        "BUS-A",
        "tf-a",
        base_url="https://new.test/exec",
        auth_reference="env:NEW",
        actor_id="operator:james",
        request_id="REQ-ROTATE",
    )

    assert updated.base_url == "https://new.test/exec"
    assert updated.auth_reference == "env:NEW"
    event = next(event for event in audit.events if event.event_type == "control_plane.integration_updated")
    assert event.data["endpoint_changed"] is True
    assert event.data["auth_reference_changed"] is True
    assert "base_url" not in event.data
    assert "auth_reference" not in event.data
    assert "new.test" not in repr(event.data)
    assert "env:NEW" not in repr(event.data)


@pytest.mark.asyncio
async def test_operator_rejects_unknown_capability_before_mutation_or_audit() -> None:
    service, registry, _cache, audit = _service()
    with pytest.raises(OperatorControlPlaneError, match="unknown capability"):
        await service.set_capability_enabled(
            "BUS-A",
            "unknown.capability",
            enabled=True,
            config=None,
            actor_id="operator:james",
            request_id="REQ-BAD",
        )
    current = await registry.get_business("BUS-A")
    assert current == BUSINESS
    assert not audit.events

@pytest.mark.asyncio
async def test_operator_cannot_assign_marketplace_capability_to_business() -> None:
    service, registry, _cache, audit = _service()

    with pytest.raises(OperatorControlPlaneError, match="platform capability"):
        await service.set_capability_enabled(
            "BUS-A",
            "marketplace",
            enabled=True,
            config=None,
            actor_id="operator:james",
            request_id="REQ-MARKETPLACE",
        )

    assert await registry.get_business("BUS-A") == BUSINESS
    assert not audit.events


@pytest.mark.asyncio
async def test_operator_registers_primary_marketplace_platform_channel() -> None:
    from ntheemba.domain.business import ChannelRole, ChannelScope, PlatformCapability

    service, registry, _cache, audit = _service()
    channel = BusinessChannel(
        "platform-marketplace",
        "waha",
        None,
        "+260970000099",
        scope=ChannelScope.PLATFORM,
        role=ChannelRole.MARKETPLACE,
        is_primary=True,
        external_session_id="ntheemba-main",
    )

    result = await service.register_channel(
        channel,
        actor_id="operator:james",
        request_id="REQ-PLATFORM",
    )

    assert result.platform_capabilities == frozenset({PlatformCapability.MARKETPLACE})
    assert (await registry.get_channel("platform-marketplace")).business_id is None
    event = next(event for event in audit.events if event.event_type == "control_plane.channel_registered")
    assert event.business_id == "__platform__"
    assert event.data["role"] == "marketplace"

@pytest.mark.asyncio
async def test_second_primary_marketplace_channel_replaces_first_primary() -> None:
    from ntheemba.domain.business import ChannelRole, ChannelScope

    service, registry, _cache, _audit = _service()
    first = BusinessChannel(
        "marketplace-1", "waha", None, "+260970000091",
        scope=ChannelScope.PLATFORM, role=ChannelRole.MARKETPLACE,
        is_primary=True, external_session_id="marketplace-session-1",
    )
    second = BusinessChannel(
        "marketplace-2", "waha", None, "+260970000092",
        scope=ChannelScope.PLATFORM, role=ChannelRole.MARKETPLACE,
        is_primary=True, external_session_id="marketplace-session-2",
    )
    await service.register_channel(first, actor_id="operator:james", request_id="REQ-P1")
    await service.register_channel(second, actor_id="operator:james", request_id="REQ-P2")

    channels = {item.channel_instance_id: item for item in await registry.list_channels()}
    assert channels["marketplace-1"].is_primary is False
    assert channels["marketplace-2"].is_primary is True


@pytest.mark.asyncio
async def test_operator_rejects_duplicate_external_channel_identity() -> None:
    service, _registry, _cache, _audit = _service()
    first = BusinessChannel(
        "channel-1", "waha", "BUS-A", "+260970000001",
        external_session_id="same-session",
    )
    second = BusinessChannel(
        "channel-2", "waha", "BUS-A", "+260970000001",
        external_session_id="same-session",
    )
    await service.register_channel(first, actor_id="operator:james", request_id="REQ-E1")
    with pytest.raises(OperatorControlPlaneError, match="already registered"):
        await service.register_channel(second, actor_id="operator:james", request_id="REQ-E2")


@pytest.mark.asyncio
@pytest.mark.parametrize("capability_id", ["marketplace", "platform.marketplace"])
async def test_operator_rejects_all_marketplace_capability_aliases(capability_id: str) -> None:
    service, registry, _cache, audit = _service()

    with pytest.raises(OperatorControlPlaneError, match="platform capability"):
        await service.set_capability_enabled(
            "BUS-A",
            capability_id,
            enabled=True,
            config=None,
            actor_id="operator:james",
            request_id=f"REQ-{capability_id}",
        )

    assert await registry.get_business("BUS-A") == BUSINESS
    assert not audit.events
