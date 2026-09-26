"""Tests for revisioned, capability-neutral runtime profile compilation."""

import json

import pytest
from ntheemba.adapters.businesses import (
    InMemoryBusinessRegistry,
    InMemoryRuntimeProfileCache,
    InMemoryUnsupportedDeclarationSink,
)
from ntheemba.adapters.tradeflow import (
    DynamicTradeFlowIntegrationResolver,
    InMemoryTradeFlowContractAdapter,
    IntegrationUnavailableError,
)
from ntheemba.application.runtime_profiles import (
    RuntimeProfileCompiler,
    RuntimeProfileConfigurationService,
    RuntimeProfileError,
)
from ntheemba.domain.business import (
    BusinessChannel,
    BusinessIntegration,
    BusinessProfile,
)
from ntheemba.domain.capabilities import Capability, CapabilityCatalogue
from ntheemba.domain.tradeflow_contract import TradeFlowOperation, TradeFlowRequest
from ntheemba.infrastructure.redis import RedisKeyspace, RedisRuntimeProfileCache
from tests.fakes.redis_runtime import FakeRedis


class CountingBusinessRegistry(InMemoryBusinessRegistry):
    """Track authoritative reads without changing registry behavior."""

    def __init__(self) -> None:
        self.delegate = _registry()
        self.integration_reads: dict[str, int] = {}

    async def get_business(self, business_id: str) -> BusinessProfile | None:
        return await self.delegate.get_business(business_id)

    async def get_channel(self, channel_instance_id: str) -> BusinessChannel | None:
        return await self.delegate.get_channel(channel_instance_id)

    async def list_businesses(self) -> tuple[BusinessProfile, ...]:
        return await self.delegate.list_businesses()

    async def list_channels(self) -> tuple[BusinessChannel, ...]:
        return await self.delegate.list_channels()

    async def list_integrations(self, business_id: str) -> tuple[BusinessIntegration, ...]:
        self.integration_reads[business_id] = self.integration_reads.get(business_id, 0) + 1
        return await self.delegate.list_integrations(business_id)

    async def register_business(self, business: BusinessProfile) -> None:
        await self.delegate.register_business(business)

    async def register_channel(self, channel: BusinessChannel) -> None:
        await self.delegate.register_channel(channel)

    async def register_integration(self, integration: BusinessIntegration) -> None:
        await self.delegate.register_integration(integration)


def _registry() -> InMemoryBusinessRegistry:
    harvest_caps = frozenset(
        {Capability.PRODUCT_CATALOGUE.value, Capability.PRODUCT_ORDER.value}
    )
    serah_caps = frozenset(
        {
            Capability.PRODUCT_CATALOGUE.value,
            Capability.SERVICE_CATALOGUE.value,
            Capability.APPOINTMENT_CREATE.value,
        }
    )
    return InMemoryBusinessRegistry(
        businesses=(
            BusinessProfile(
                "harvest",
                "Harvest",
                "tradeflow_standard",
                harvest_caps,
                business_type="retail",
                runtime_revision=1,
                capability_config={
                    Capability.PRODUCT_ORDER.value: {"delivery_required": False}
                },
            ),
            BusinessProfile(
                "serah",
                "Serah's Glow",
                "tradeflow_serahs",
                serah_caps,
                business_type="beauty",
                runtime_revision=3,
                capability_config={
                    Capability.APPOINTMENT_CREATE.value: {"requires_staff": True}
                },
            ),
        ),
        channels=(
            BusinessChannel("wa-harvest", "openwa", "harvest", "+260970000001"),
            BusinessChannel("wa-serah", "openwa", "serah", "+260970000002"),
        ),
        integrations=(
            BusinessIntegration(
                "harvest-tradeflow",
                "harvest",
                "tradeflow_standard",
                "https://tradeflow.local/harvest",
                provider="google_apps_script",
                api_version="tradeflow.ntheemba.v1",
                auth_reference="script_properties:NTHEEMBA_API_TOKEN",
                status="testing",
                capabilities=harvest_caps,
            ),
            BusinessIntegration(
                "serah-tradeflow",
                "serah",
                "tradeflow_serahs",
                "https://tradeflow.local/serah",
                provider="google_apps_script",
                api_version="tradeflow.ntheemba.v1",
                auth_reference="script_properties:NTHEEMBA_API_TOKEN",
                status="testing",
                capabilities=serah_caps,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_harvest_profile_allows_catalogue_order_and_has_no_booking_integration() -> None:
    compiler = RuntimeProfileCompiler(
        registry=_registry(),
        catalogue=CapabilityCatalogue.canonical(),
        cache=InMemoryRuntimeProfileCache(),
    )

    profile = await compiler.resolve_channel("wa-harvest")

    assert profile.integration_for(Capability.PRODUCT_CATALOGUE) is not None
    assert profile.integration_for(Capability.PRODUCT_ORDER) is not None
    assert profile.integration_for(Capability.APPOINTMENT_CREATE) is None


@pytest.mark.asyncio
async def test_serah_profile_routes_booking_through_configured_integration() -> None:
    compiler = RuntimeProfileCompiler(
        registry=_registry(),
        catalogue=CapabilityCatalogue.canonical(),
        cache=InMemoryRuntimeProfileCache(),
    )

    profile = await compiler.resolve_channel("wa-serah")
    integration = profile.integration_for(Capability.APPOINTMENT_CREATE)

    assert integration is not None
    assert integration.integration_id == "serah-tradeflow"
    assert integration.adapter_type == "tradeflow_serahs"
    context = profile.context_for(Capability.APPOINTMENT_CREATE)
    assert context.integration == integration
    assert context.runtime_revision == 3
    assert profile.business.capability_config[Capability.APPOINTMENT_CREATE.value] == {
        "requires_staff": True
    }


@pytest.mark.asyncio
async def test_redis_loss_reloads_postgres_authoritative_configuration() -> None:
    registry = CountingBusinessRegistry()
    redis = FakeRedis()
    cache = RedisRuntimeProfileCache(redis, RedisKeyspace("ntheemba", "test"))
    compiler = RuntimeProfileCompiler(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        cache=cache,
    )

    first = await compiler.resolve_channel("wa-serah")
    assert registry.integration_reads["serah"] == 1

    redis.values.clear()
    redis.expiries.clear()
    second = await compiler.resolve_channel("wa-serah")

    assert registry.integration_reads["serah"] == 2
    assert first.to_json() == second.to_json()
    assert second.integration_for(Capability.APPOINTMENT_CREATE) is not None


@pytest.mark.asyncio
async def test_runtime_revision_change_ignores_stale_cached_profile() -> None:
    registry = CountingBusinessRegistry()
    redis = FakeRedis()
    cache = RedisRuntimeProfileCache(redis, RedisKeyspace("ntheemba", "test"))
    compiler = RuntimeProfileCompiler(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        cache=cache,
    )
    await compiler.resolve_channel("wa-harvest")
    assert registry.integration_reads["harvest"] == 1

    updated = BusinessProfile(
        "harvest",
        "Harvest",
        "tradeflow_standard",
        frozenset({Capability.PRODUCT_CATALOGUE.value}),
        business_type="retail",
        runtime_revision=2,
    )
    await registry.register_business(updated)
    await registry.register_integration(
        BusinessIntegration(
            "harvest-tradeflow",
            "harvest",
            "tradeflow_standard",
            "https://tradeflow.local/harvest",
            capabilities=frozenset({Capability.PRODUCT_CATALOGUE.value}),
        )
    )

    profile = await compiler.resolve_channel("wa-harvest")

    assert registry.integration_reads["harvest"] == 2
    assert profile.business.runtime_revision == 2
    assert profile.integration_for(Capability.PRODUCT_CATALOGUE) is not None
    assert profile.integration_for(Capability.PRODUCT_ORDER) is None


@pytest.mark.asyncio
async def test_cache_rejects_payload_with_stale_runtime_revision_at_current_key() -> None:
    registry = CountingBusinessRegistry()
    redis = FakeRedis()
    cache = RedisRuntimeProfileCache(redis, RedisKeyspace("ntheemba", "test"))
    compiler = RuntimeProfileCompiler(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        cache=cache,
    )

    profile = await compiler.resolve_channel("wa-harvest")
    stale_payload = json.loads(profile.to_json())
    stale_payload["business"]["runtime_revision"] = 0
    await cache.set(
        "harvest",
        "wa-harvest",
        1,
        json.dumps(stale_payload),
        ttl_seconds=60,
    )

    reloaded = await compiler.resolve_channel("wa-harvest")

    assert registry.integration_reads["harvest"] == 2
    assert reloaded.business.runtime_revision == 1


@pytest.mark.asyncio
async def test_runtime_cache_is_channel_scoped_for_multi_channel_business() -> None:
    registry = _registry()
    await registry.register_channel(
        BusinessChannel("wa-serah-alt", "openwa", "serah", "+260970000099")
    )
    cache = InMemoryRuntimeProfileCache()
    compiler = RuntimeProfileCompiler(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        cache=cache,
    )

    main = await compiler.resolve_channel("wa-serah")
    alt = await compiler.resolve_channel("wa-serah-alt")

    assert main.channel.channel_instance_id == "wa-serah"
    assert main.channel.phone_e164 == "+260970000002"
    assert alt.channel.channel_instance_id == "wa-serah-alt"
    assert alt.channel.phone_e164 == "+260970000099"


@pytest.mark.asyncio
async def test_cached_runtime_profile_excludes_channel_phone_and_integration_config() -> None:
    registry = _registry()
    await registry.register_business(
        BusinessProfile(
            "serah",
            "Serah's Glow",
            "tradeflow_serahs",
            frozenset(
                {
                    Capability.PRODUCT_CATALOGUE.value,
                    Capability.SERVICE_CATALOGUE.value,
                    Capability.APPOINTMENT_CREATE.value,
                }
            ),
            business_type="beauty",
            runtime_revision=4,
            capability_config={
                Capability.APPOINTMENT_CREATE.value: {
                    "private_api_key": "super-secret-capability-value"
                }
            },
        )
    )
    await registry.register_integration(
        BusinessIntegration(
            "serah-tradeflow",
            "serah",
            "tradeflow_serahs",
            "https://tradeflow.local/serah",
            provider="google_apps_script",
            api_version="tradeflow.ntheemba.v1",
            auth_reference="script_properties:NTHEEMBA_API_TOKEN",
            status="testing",
            capabilities=frozenset(
                {
                    Capability.PRODUCT_CATALOGUE.value,
                    Capability.SERVICE_CATALOGUE.value,
                    Capability.APPOINTMENT_CREATE.value,
                }
            ),
            config={"private_policy_value": "do-not-cache"},
        )
    )
    redis = FakeRedis()
    cache = RedisRuntimeProfileCache(redis, RedisKeyspace("ntheemba", "test"))
    compiler = RuntimeProfileCompiler(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        cache=cache,
    )

    profile = await compiler.resolve_channel("wa-serah")
    payload = await cache.get(
        profile.business.business_id,
        profile.channel.channel_instance_id,
        profile.business.runtime_revision,
    )

    assert payload is not None
    data = json.loads(payload)
    assert "phone_e164" not in data["channel"]
    assert "capability_config" not in data["business"]
    assert "+260970000002" not in payload
    assert "super-secret-capability-value" not in payload
    assert all("config" not in integration for integration in data["integrations"])
    assert all("auth_reference" not in integration for integration in data["integrations"])
    assert "NTHEEMBA_API_TOKEN" not in payload
    assert "private_api_key" not in payload
    assert data["integrations"][0]["provider"] == "google_apps_script"
    assert data["integrations"][0]["api_version"] == "tradeflow.ntheemba.v1"
    assert data["integrations"][0]["status"] == "testing"


@pytest.mark.asyncio
async def test_capability_update_invalidates_cached_runtime_profile() -> None:
    registry = CountingBusinessRegistry()
    redis = FakeRedis()
    cache = RedisRuntimeProfileCache(redis, RedisKeyspace("ntheemba", "test"))
    compiler = RuntimeProfileCompiler(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        cache=cache,
    )
    configuration = RuntimeProfileConfigurationService(
        registry=registry,
        compiler=compiler,
    )

    original = await compiler.resolve_channel("wa-harvest")
    original_key = RedisKeyspace("ntheemba", "test").runtime_profile(
        "harvest",
        "wa-harvest",
        original.business.runtime_revision,
    )
    assert original_key in redis.values

    await configuration.register_business(
        BusinessProfile(
            "harvest",
            "Harvest",
            "tradeflow_standard",
            frozenset({Capability.PRODUCT_CATALOGUE.value}),
            business_type="retail",
            runtime_revision=2,
        )
    )

    assert original_key not in redis.values
    updated = await compiler.resolve_channel("wa-harvest")
    assert updated.integration_for(Capability.PRODUCT_ORDER) is None


@pytest.mark.asyncio
async def test_disabling_serah_booking_increments_revision_and_excludes_booking() -> None:
    registry = CountingBusinessRegistry()
    redis = FakeRedis()
    cache = RedisRuntimeProfileCache(redis, RedisKeyspace("ntheemba", "test"))
    compiler = RuntimeProfileCompiler(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        cache=cache,
    )
    configuration = RuntimeProfileConfigurationService(
        registry=registry,
        compiler=compiler,
    )

    original = await compiler.resolve_channel("wa-serah")
    assert original.business.runtime_revision == 3
    assert original.integration_for(Capability.APPOINTMENT_CREATE) is not None

    updated_business = await configuration.set_capability_enabled(
        "serah",
        Capability.APPOINTMENT_CREATE.value,
        enabled=False,
    )
    updated = await compiler.resolve_channel("wa-serah")

    assert updated_business.runtime_revision == 4
    assert updated.business.runtime_revision == 4
    assert Capability.APPOINTMENT_CREATE not in updated.capabilities
    assert updated.integration_for(Capability.APPOINTMENT_CREATE) is None


@pytest.mark.asyncio
async def test_disabling_business_invalidates_profile_and_blocks_channel() -> None:
    registry = CountingBusinessRegistry()
    cache = InMemoryRuntimeProfileCache()
    compiler = RuntimeProfileCompiler(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        cache=cache,
    )
    configuration = RuntimeProfileConfigurationService(
        registry=registry,
        compiler=compiler,
    )

    original = await compiler.resolve_channel("wa-harvest")
    updated_business = await configuration.set_business_enabled("harvest", enabled=False)

    assert updated_business.runtime_revision == original.business.runtime_revision + 1
    assert updated_business.enabled is False
    with pytest.raises(RuntimeProfileError, match="business unavailable"):
        await compiler.resolve_channel("wa-harvest")


@pytest.mark.asyncio
async def test_business_enablement_update_is_idempotent() -> None:
    registry = _registry()
    compiler = RuntimeProfileCompiler(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        cache=InMemoryRuntimeProfileCache(),
    )
    configuration = RuntimeProfileConfigurationService(
        registry=registry,
        compiler=compiler,
    )

    unchanged = await configuration.set_business_enabled("harvest", enabled=True)

    assert unchanged.runtime_revision == 1


@pytest.mark.asyncio
async def test_unknown_capability_is_rejected_without_runtime_mutation() -> None:
    registry = _registry()
    compiler = RuntimeProfileCompiler(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        cache=InMemoryRuntimeProfileCache(),
    )
    configuration = RuntimeProfileConfigurationService(registry=registry, compiler=compiler)

    with pytest.raises(RuntimeProfileError, match="unknown capability"):
        await configuration.set_capability_enabled("harvest", "not.a.capability", enabled=True)

    unchanged = await registry.get_business("harvest")
    assert unchanged is not None
    assert unchanged.runtime_revision == 1


@pytest.mark.asyncio
async def test_integration_update_invalidates_cached_runtime_profile() -> None:
    registry = CountingBusinessRegistry()
    redis = FakeRedis()
    cache = RedisRuntimeProfileCache(redis, RedisKeyspace("ntheemba", "test"))
    compiler = RuntimeProfileCompiler(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        cache=cache,
    )
    configuration = RuntimeProfileConfigurationService(
        registry=registry,
        compiler=compiler,
    )

    original = await compiler.resolve_channel("wa-serah")
    original_key = RedisKeyspace("ntheemba", "test").runtime_profile(
        "serah",
        "wa-serah",
        original.business.runtime_revision,
    )

    await configuration.register_integration(
        BusinessIntegration(
            "serah-tradeflow",
            "serah",
            "tradeflow_serahs",
            "https://tradeflow.local/serah",
            status="disabled",
            capabilities=frozenset({Capability.APPOINTMENT_CREATE.value}),
            config={"private_policy_value": "do-not-cache"},
        )
    )

    assert original_key not in redis.values
    updated = await compiler.resolve_channel("wa-serah")
    assert updated.integration_for(Capability.APPOINTMENT_CREATE) is None


@pytest.mark.asyncio
async def test_disabled_or_inactive_integration_does_not_compile_into_runtime() -> None:
    caps = frozenset({Capability.PRODUCT_CATALOGUE.value})
    registry = InMemoryBusinessRegistry(
        businesses=(
            BusinessProfile(
                "disabled-shop",
                "Disabled Shop",
                "tradeflow_standard",
                caps,
                runtime_revision=1,
            ),
        ),
        channels=(BusinessChannel("wa-disabled", "openwa", "disabled-shop", "+260970000003"),),
        integrations=(
            BusinessIntegration(
                "disabled-tradeflow",
                "disabled-shop",
                "tradeflow_standard",
                "https://tradeflow.local/disabled",
                status="disabled",
                capabilities=caps,
            ),
        ),
    )
    compiler = RuntimeProfileCompiler(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        cache=InMemoryRuntimeProfileCache(),
    )

    profile = await compiler.resolve_channel("wa-disabled")

    assert profile.integration_for(Capability.PRODUCT_CATALOGUE) is None


@pytest.mark.asyncio
async def test_dynamic_resolver_denies_harvest_booking_without_adapter_call() -> None:
    called = False

    def factory(context):
        nonlocal called
        called = True
        return InMemoryTradeFlowContractAdapter(
            business_id=context.business.business_id,
            handlers={},
        )

    compiler = RuntimeProfileCompiler(
        registry=_registry(),
        catalogue=CapabilityCatalogue.canonical(),
        cache=InMemoryRuntimeProfileCache(),
    )
    profile = await compiler.resolve_channel("wa-harvest")
    resolver = DynamicTradeFlowIntegrationResolver(
        factories={"tradeflow_standard": factory},
        observations=InMemoryUnsupportedDeclarationSink(),
    )

    with pytest.raises(IntegrationUnavailableError):
        resolver.resolve(profile.context_for(Capability.APPOINTMENT_CREATE))

    assert called is False


@pytest.mark.asyncio
async def test_dynamic_resolver_uses_serah_configured_integration() -> None:
    used: list[str] = []
    compiler = RuntimeProfileCompiler(
        registry=_registry(),
        catalogue=CapabilityCatalogue.canonical(),
        cache=InMemoryRuntimeProfileCache(),
    )
    profile = await compiler.resolve_channel("wa-serah")

    def factory(context):
        assert context.integration is not None
        used.append(context.integration.integration_id)
        return InMemoryTradeFlowContractAdapter(
            business_id=context.business.business_id,
            handlers={
                TradeFlowOperation.APPOINTMENT_CHECK_AVAILABILITY: (
                    lambda _request: async_ok({"slots": []})
                )
            },
        )

    resolver = DynamicTradeFlowIntegrationResolver(
        factories={"tradeflow_serahs": factory},
        observations=InMemoryUnsupportedDeclarationSink(),
    )

    adapter = resolver.resolve(profile.context_for(Capability.APPOINTMENT_CREATE))
    response = await adapter.execute(
        TradeFlowRequest(
            request_id="request-serah-booking",
            business_id="serah",
            operation=TradeFlowOperation.APPOINTMENT_CHECK_AVAILABILITY,
            payload={"service_id": "svc-1", "date": "2026-08-23"},
        )
    )

    assert used == ["serah-tradeflow"]
    assert response.ok is True
    assert response.data == {"slots": []}


@pytest.mark.asyncio
async def test_dynamic_resolver_binds_each_business_to_its_configured_url() -> None:
    used_urls: list[str] = []
    compiler = RuntimeProfileCompiler(
        registry=_registry(),
        catalogue=CapabilityCatalogue.canonical(),
        cache=InMemoryRuntimeProfileCache(),
    )

    def factory(context):
        assert context.integration is not None
        used_urls.append(context.integration.base_url)
        return InMemoryTradeFlowContractAdapter(
            business_id=context.business.business_id,
            handlers={},
        )

    resolver = DynamicTradeFlowIntegrationResolver(
        factories={
            "tradeflow_standard": factory,
            "tradeflow_serahs": factory,
        },
        observations=InMemoryUnsupportedDeclarationSink(),
    )

    harvest = await compiler.resolve_channel("wa-harvest")
    serah = await compiler.resolve_channel("wa-serah")

    resolver.resolve(harvest.context_for(Capability.PRODUCT_ORDER))
    resolver.resolve(serah.context_for(Capability.APPOINTMENT_CREATE))

    assert used_urls == [
        "https://tradeflow.local/harvest",
        "https://tradeflow.local/serah",
    ]


async def async_ok(payload):
    return payload

@pytest.mark.asyncio
async def test_cache_hit_rehydrates_secret_bearing_configuration_from_registry() -> None:
    registry = _registry()
    cache = InMemoryRuntimeProfileCache()
    compiler = RuntimeProfileCompiler(
        registry=registry,
        catalogue=CapabilityCatalogue.canonical(),
        cache=cache,
    )

    first = await compiler.resolve_channel("wa-serah")
    first_integration = first.integration_for(Capability.APPOINTMENT_CREATE)
    assert first_integration is not None
    assert first_integration.auth_reference == "script_properties:NTHEEMBA_API_TOKEN"

    # Simulate a durable configuration update that keeps the same secret-free routing
    # projection.  Redis must not contain these values, but a cache hit must still return
    # the authoritative PostgreSQL/in-memory registry values.
    await registry.register_business(
        BusinessProfile(
            "serah",
            "Serah's Glow",
            "tradeflow_serahs",
            first.business.declared_capabilities,
            business_type="beauty",
            runtime_revision=first.business.runtime_revision,
            capability_config={
                Capability.APPOINTMENT_CREATE.value: {"requires_staff": False}
            },
        )
    )
    await registry.register_integration(
        BusinessIntegration(
            "serah-tradeflow",
            "serah",
            "tradeflow_serahs",
            "https://tradeflow.local/serah",
            provider="google_apps_script",
            api_version="tradeflow.ntheemba.v1",
            auth_reference="env:SERAHS_TRADEFLOW_TOKEN_V2",
            status="testing",
            capabilities=first_integration.capabilities,
            config={"timeout_seconds": 7},
        )
    )

    second = await compiler.resolve_channel("wa-serah")
    integration = second.integration_for(Capability.APPOINTMENT_CREATE)

    assert integration is not None
    assert integration.auth_reference == "env:SERAHS_TRADEFLOW_TOKEN_V2"
    assert dict(integration.config) == {"timeout_seconds": 7}
    assert second.business.capability_config[Capability.APPOINTMENT_CREATE.value] == {
        "requires_staff": False
    }
