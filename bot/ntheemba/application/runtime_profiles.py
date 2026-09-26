"""Compile tenant runtime profiles from business records and integrations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecodeError
from types import MappingProxyType

from ntheemba.domain.business import (
    BusinessChannel,
    ChannelScope,
    BusinessIntegration,
    BusinessProfile,
    ResolvedBusinessContext,
)
from ntheemba.domain.capabilities import Capability, CapabilityCatalogue
from ntheemba.ports.businesses import (
    BusinessRegistry,
    MutableBusinessRegistry,
    RuntimeProfileCache,
)


class RuntimeProfileError(LookupError):
    """Raised when a business profile cannot be compiled safely."""


@dataclass(frozen=True, slots=True)
class CompiledRuntimeProfile:
    """One revisioned, integration-aware business runtime profile."""

    business: BusinessProfile
    channel: BusinessChannel
    capabilities: frozenset[Capability]
    integrations: tuple[BusinessIntegration, ...]
    rejected_declarations: frozenset[str] = frozenset()

    def integration_for(self, capability: Capability) -> BusinessIntegration | None:
        """Return the enabled integration configured for a canonical capability."""

        if capability not in self.capabilities:
            return None
        for integration in self.integrations:
            if integration.enabled and capability.value in integration.capabilities:
                return integration
        return None

    def context_for(self, capability: Capability | None = None) -> ResolvedBusinessContext:
        """Build a resolved context with the integration selected for an action."""

        integration = self.integration_for(capability) if capability else None
        return ResolvedBusinessContext(
            business=self.business,
            channel=self.channel,
            capabilities=self.capabilities,
            rejected_declarations=self.rejected_declarations,
            integrations=self.integrations,
            integration=integration,
            runtime_revision=self.business.runtime_revision,
        )

    def to_json(self) -> str:
        """Serialize only non-secret runtime routing data for Redis."""

        return json.dumps(
            {
                "business": {
                    "business_id": self.business.business_id,
                    "display_name": self.business.display_name,
                    "adapter_type": self.business.adapter_type,
                    "declared_capabilities": sorted(self.business.declared_capabilities),
                    "enabled": self.business.enabled,
                    "business_type": self.business.business_type,
                    "description": self.business.description,
                    "runtime_revision": self.business.runtime_revision,
                },
                "channel": {
                    "channel_instance_id": self.channel.channel_instance_id,
                    "provider": self.channel.provider,
                    "business_id": self.channel.business_id,
                    "enabled": self.channel.enabled,
                },
                "capabilities": sorted(item.value for item in self.capabilities),
                "rejected_declarations": sorted(self.rejected_declarations),
                "integrations": [
                    {
                        "integration_id": item.integration_id,
                        "business_id": item.business_id,
                        "provider": item.provider,
                        "adapter_type": item.adapter_type,
                        "base_url": item.base_url,
                        "api_version": item.api_version,
                        "status": item.status,
                        "enabled": item.enabled,
                        "capabilities": sorted(item.capabilities),
                    }
                    for item in self.integrations
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(
        cls,
        payload: str,
        *,
        channel: BusinessChannel,
    ) -> CompiledRuntimeProfile:
        data = json.loads(payload)
        business_data = data["business"]
        channel_data = data["channel"]
        if str(channel_data["channel_instance_id"]) != channel.channel_instance_id:
            raise RuntimeProfileError("cached profile channel mismatch")
        if str(channel_data["business_id"]) != channel.business_id:
            raise RuntimeProfileError("cached profile business mismatch")
        return cls(
            business=BusinessProfile(
                business_id=str(business_data["business_id"]),
                display_name=str(business_data["display_name"]),
                adapter_type=str(business_data["adapter_type"]),
                declared_capabilities=frozenset(business_data["declared_capabilities"]),
                enabled=bool(business_data["enabled"]),
                business_type=str(business_data.get("business_type", "")),
                description=str(business_data.get("description", "")),
                runtime_revision=int(business_data.get("runtime_revision", 0)),
                capability_config=MappingProxyType(
                    {
                        str(capability_id): MappingProxyType(dict(config or {}))
                        for capability_id, config in business_data.get(
                            "capability_config", {}
                        ).items()
                    }
                ),
            ),
            channel=channel,
            capabilities=frozenset(Capability(item) for item in data["capabilities"]),
            rejected_declarations=frozenset(
                str(item) for item in data.get("rejected_declarations", ())
            ),
            integrations=tuple(
                BusinessIntegration(
                    integration_id=str(item["integration_id"]),
                    business_id=str(item["business_id"]),
                    provider=str(item.get("provider", "google_apps_script")),
                    adapter_type=str(item["adapter_type"]),
                    base_url=str(item["base_url"]),
                    api_version=str(item.get("api_version", "tradeflow.ntheemba.v1")),
                    status=str(item.get("status", "active")),
                    enabled=bool(item["enabled"]),
                    capabilities=frozenset(str(cap) for cap in item["capabilities"]),
                    config=MappingProxyType({}),
                )
                for item in data.get("integrations", ())
            ),
        )


class RuntimeProfileCompiler:
    """Compile and cache a runtime profile from PostgreSQL-authoritative records."""

    def __init__(
        self,
        *,
        registry: BusinessRegistry,
        catalogue: CapabilityCatalogue,
        cache: RuntimeProfileCache | None = None,
        ttl_seconds: int = 300,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        self.registry = registry
        self.catalogue = catalogue
        self.cache = cache
        self.ttl_seconds = ttl_seconds

    async def resolve_channel(self, channel_instance_id: str) -> CompiledRuntimeProfile:
        """Resolve a channel and compile its active business runtime profile."""

        channel = await self.registry.get_channel(channel_instance_id)
        if channel is None or not channel.enabled:
            raise RuntimeProfileError(f"unknown channel {channel_instance_id!r}")
        if channel.scope is not ChannelScope.BUSINESS or channel.business_id is None:
            raise RuntimeProfileError("platform channels do not have business runtime profiles")
        business = await self.registry.get_business(channel.business_id)
        if business is None or not business.enabled:
            raise RuntimeProfileError(f"business unavailable {channel.business_id!r}")
        return await self.compile(business, channel)

    async def compile(
        self,
        business: BusinessProfile,
        channel: BusinessChannel,
    ) -> CompiledRuntimeProfile:
        """Compile a runtime while keeping secret-bearing configuration authoritative.

        Redis deliberately stores only non-secret routing data.  Even on a cache hit we
        reload integration records from the durable registry so auth references, private
        integration configuration, and business capability configuration never need to be
        copied into Redis.  The cached routing projection is used only when it still
        matches the authoritative records for the same runtime revision.
        """

        if channel.scope is not ChannelScope.BUSINESS or channel.business_id != business.business_id:
            raise RuntimeProfileError("channel business does not match profile")

        declaration = self.catalogue.validate_declarations(business.declared_capabilities)
        integrations = await self.registry.list_integrations(business.business_id)
        supported_integrations = self._supported_integrations(
            business,
            declaration.supported,
            integrations,
        )

        if self.cache is not None:
            cached = await self.cache.get(
                business.business_id,
                channel.channel_instance_id,
                business.runtime_revision,
            )
            if cached is not None:
                try:
                    cached_profile = CompiledRuntimeProfile.from_json(
                        cached,
                        channel=channel,
                    )
                except (JSONDecodeError, KeyError, TypeError, ValueError, RuntimeProfileError):
                    cached_profile = None
                if (
                    cached_profile is not None
                    and cached_profile.business.business_id == business.business_id
                    and cached_profile.business.runtime_revision == business.runtime_revision
                    and cached_profile.capabilities == declaration.supported
                    and cached_profile.rejected_declarations == declaration.unknown
                    and self._routing_signature(cached_profile.integrations)
                    == self._routing_signature(supported_integrations)
                ):
                    return CompiledRuntimeProfile(
                        business=business,
                        channel=channel,
                        capabilities=declaration.supported,
                        rejected_declarations=declaration.unknown,
                        integrations=supported_integrations,
                    )

        profile = CompiledRuntimeProfile(
            business=business,
            channel=channel,
            capabilities=declaration.supported,
            rejected_declarations=declaration.unknown,
            integrations=supported_integrations,
        )
        if self.cache is not None:
            await self.cache.set(
                business.business_id,
                channel.channel_instance_id,
                business.runtime_revision,
                profile.to_json(),
                ttl_seconds=self.ttl_seconds,
            )
        return profile

    def _supported_integrations(
        self,
        business: BusinessProfile,
        capabilities: frozenset[Capability],
        integrations: tuple[BusinessIntegration, ...],
    ) -> tuple[BusinessIntegration, ...]:
        """Return authoritative integrations eligible for this compiled runtime."""

        return tuple(
            integration
            for integration in integrations
            if integration.enabled
            and integration.status in {"active", "testing"}
            and integration.business_id == business.business_id
            and capabilities.intersection(
                Capability(item)
                for item in integration.capabilities
                if self.catalogue.contains(item)
            )
        )

    @staticmethod
    def _routing_signature(
        integrations: tuple[BusinessIntegration, ...],
    ) -> tuple[tuple[object, ...], ...]:
        """Return the secret-free routing fields that are allowed to live in Redis."""

        return tuple(
            (
                item.integration_id,
                item.business_id,
                item.provider,
                item.adapter_type,
                item.base_url,
                item.api_version,
                item.status,
                item.enabled,
                tuple(sorted(item.capabilities)),
            )
            for item in integrations
        )

    async def invalidate(self, business_id: str) -> None:
        """Invalidate stale runtime state after capability or integration changes."""

        if self.cache is not None:
            await self.cache.invalidate(business_id)


class RuntimeProfileConfigurationService:
    """Write runtime configuration and clear cached profiles for the affected business."""

    def __init__(
        self,
        *,
        registry: MutableBusinessRegistry,
        compiler: RuntimeProfileCompiler,
    ) -> None:
        self.registry = registry
        self.compiler = compiler

    async def register_business(self, business: BusinessProfile) -> None:
        """Persist capability changes and invalidate cached compiled runtimes."""

        await self.registry.register_business(business)
        await self.compiler.invalidate(business.business_id)

    async def register_channel(self, channel: BusinessChannel) -> None:
        """Persist channel changes and invalidate cached compiled runtimes."""

        await self.registry.register_channel(channel)
        if channel.business_id is not None:
            await self.compiler.invalidate(channel.business_id)

    async def register_integration(self, integration: BusinessIntegration) -> None:
        """Persist integration changes and invalidate cached compiled runtimes."""

        await self.registry.register_integration(integration)
        await self.compiler.invalidate(integration.business_id)

    async def register_shop(self, shop: "BusinessShop") -> None:
        """Persist a shop routing projection and invalidate compiled runtimes."""

        await self.registry.register_shop(shop)
        await self.compiler.invalidate(shop.business_id)

    async def set_capability_enabled(
        self,
        business_id: str,
        capability_id: str,
        *,
        enabled: bool,
        config: dict[str, object] | None = None,
    ) -> BusinessProfile:
        """Enable or disable one capability and bump the runtime revision."""

        if not CapabilityCatalogue.canonical().contains(capability_id):
            raise RuntimeProfileError(f"unknown capability {capability_id!r}")
        business = await self.registry.get_business(business_id)
        if business is None:
            raise RuntimeProfileError(f"unknown business {business_id!r}")
        capabilities = set(business.declared_capabilities)
        capability_config = {
            key: dict(value) for key, value in business.capability_config.items()
        }
        if enabled:
            capabilities.add(capability_id)
            if config is not None:
                capability_config[capability_id] = dict(config)
        else:
            capabilities.discard(capability_id)
            capability_config.pop(capability_id, None)
        updated = BusinessProfile(
            business_id=business.business_id,
            display_name=business.display_name,
            adapter_type=business.adapter_type,
            declared_capabilities=frozenset(capabilities),
            enabled=business.enabled,
            business_type=business.business_type,
            description=business.description,
            runtime_revision=business.runtime_revision + 1,
            capability_config=MappingProxyType(
                {
                    key: MappingProxyType(value)
                    for key, value in capability_config.items()
                }
            ),
        )
        await self.registry.register_business(updated)
        await self.compiler.invalidate(business_id)
        return updated

    async def set_business_enabled(
        self,
        business_id: str,
        *,
        enabled: bool,
    ) -> BusinessProfile:
        """Enable or disable a business and invalidate its compiled runtime."""

        business = await self.registry.get_business(business_id)
        if business is None:
            raise RuntimeProfileError(f"unknown business {business_id!r}")
        if business.enabled == enabled:
            return business
        updated = BusinessProfile(
            business_id=business.business_id,
            display_name=business.display_name,
            adapter_type=business.adapter_type,
            declared_capabilities=business.declared_capabilities,
            enabled=enabled,
            business_type=business.business_type,
            description=business.description,
            runtime_revision=business.runtime_revision + 1,
            capability_config=business.capability_config,
        )
        await self.registry.register_business(updated)
        await self.compiler.invalidate(business_id)
        return updated
