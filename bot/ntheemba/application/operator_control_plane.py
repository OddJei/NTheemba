"""Audited operator mutations for Ntheemba's durable business control plane."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import Any

from ntheemba.application.runtime_profiles import (
    RuntimeProfileConfigurationService,
    RuntimeProfileError,
)
from ntheemba.domain.business import (
    PLATFORM_CAPABILITY_IDS, BusinessShop, ChannelBinding, ChannelScope, BusinessChannel, BusinessIntegration, BusinessProfile,
)
from ntheemba.domain.capabilities import CapabilityCatalogue
from ntheemba.ports.audit import AuditEvent, AuditSink
from ntheemba.ports.businesses import MutableBusinessRegistry


class OperatorControlPlaneError(ValueError):
    """Safe validation error for operator configuration requests."""


class OperatorControlPlaneService:
    """Apply tenant configuration changes with cache invalidation and audit evidence."""

    def __init__(
        self,
        *,
        registry: MutableBusinessRegistry,
        configuration: RuntimeProfileConfigurationService,
        audit: AuditSink,
    ) -> None:
        self.registry = registry
        self.configuration = configuration
        self.audit = audit
        self.catalogue = CapabilityCatalogue.canonical()

    @staticmethod
    def _identity(actor_id: str, request_id: str) -> tuple[str, str]:
        actor = actor_id.strip()
        request = request_id.strip()
        if not actor:
            raise OperatorControlPlaneError("actor_id must not be empty")
        if not request:
            raise OperatorControlPlaneError("request_id must not be empty")
        return actor, request

    async def _requested(
        self,
        *,
        business_id: str,
        actor_id: str,
        request_id: str,
        action: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        await self.audit.record(
            AuditEvent(
                event_type="control_plane.mutation_requested",
                request_id=request_id,
                business_id=business_id,
                data={"actor_id": actor_id, "action": action, **(data or {})},
            )
        )

    async def _completed(
        self,
        *,
        business_id: str,
        actor_id: str,
        request_id: str,
        action: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        await self.audit.record(
            AuditEvent(
                event_type=f"control_plane.{action}",
                request_id=request_id,
                business_id=business_id,
                data={"actor_id": actor_id, **(data or {})},
            )
        )

    async def register_business(
        self,
        business: BusinessProfile,
        *,
        actor_id: str,
        request_id: str,
    ) -> BusinessProfile:
        actor, request = self._identity(actor_id, request_id)
        declaration = self.catalogue.validate_declarations(business.declared_capabilities)
        if declaration.unknown:
            raise OperatorControlPlaneError(
                f"unknown capabilities: {', '.join(sorted(declaration.unknown))}"
            )
        await self._requested(
            business_id=business.business_id,
            actor_id=actor,
            request_id=request,
            action="business_register",
        )
        await self.configuration.register_business(business)
        persisted = await self.registry.get_business(business.business_id)
        result = persisted or business
        await self._completed(
            business_id=business.business_id,
            actor_id=actor,
            request_id=request,
            action="business_registered",
            data={
                "enabled": result.enabled,
                "capabilities": sorted(result.declared_capabilities),
                "runtime_revision": result.runtime_revision,
            },
        )
        return result

    async def register_channel(
        self,
        channel: ChannelBinding,
        *,
        actor_id: str,
        request_id: str,
    ) -> ChannelBinding:
        actor, request = self._identity(actor_id, request_id)
        audit_scope = channel.business_id or "__platform__"
        if channel.scope is ChannelScope.BUSINESS:
            if channel.business_id is None:
                raise OperatorControlPlaneError("business channel requires business_id")
            business = await self.registry.get_business(channel.business_id)
            if business is None:
                raise OperatorControlPlaneError(f"unknown business {channel.business_id!r}")
        existing = await self.registry.get_channel(channel.channel_instance_id)
        if existing is not None and (
            existing.business_id != channel.business_id or existing.scope != channel.scope
        ):
            raise OperatorControlPlaneError("channel belongs to another business or scope; ownership is immutable")
        await self._requested(
            business_id=audit_scope,
            actor_id=actor,
            request_id=request,
            action="channel_register",
            data={
                "channel_instance_id": channel.channel_instance_id,
                "scope": channel.scope.value,
                "role": channel.role.value,
            },
        )
        try:
            await self.configuration.register_channel(channel)
        except (RuntimeProfileError, ValueError) as error:
            raise OperatorControlPlaneError(str(error)) from error
        await self._completed(
            business_id=audit_scope,
            actor_id=actor,
            request_id=request,
            action="channel_registered",
            data={
                "channel_instance_id": channel.channel_instance_id,
                "provider": channel.provider,
                "scope": channel.scope.value,
                "role": channel.role.value,
                "is_primary": channel.is_primary,
                "enabled": channel.enabled,
            },
        )
        return channel

    async def register_integration(
        self,
        integration: BusinessIntegration,
        *,
        actor_id: str,
        request_id: str,
    ) -> BusinessIntegration:
        actor, request = self._identity(actor_id, request_id)
        business = await self.registry.get_business(integration.business_id)
        if business is None:
            raise OperatorControlPlaneError(f"unknown business {integration.business_id!r}")
        unknown = sorted(
            capability
            for capability in integration.capabilities
            if not self.catalogue.contains(capability)
        )
        if unknown:
            raise OperatorControlPlaneError(
                f"unknown integration capabilities: {', '.join(unknown)}"
            )
        existing = self._find_integration(
            await self.registry.list_integrations(integration.business_id),
            integration.integration_id,
        )
        if existing is not None and existing.business_id != integration.business_id:
            raise OperatorControlPlaneError("integration belongs to another business")
        await self._requested(
            business_id=integration.business_id,
            actor_id=actor,
            request_id=request,
            action="integration_register",
            data={"integration_id": integration.integration_id},
        )
        await self.configuration.register_integration(integration)
        await self._completed(
            business_id=integration.business_id,
            actor_id=actor,
            request_id=request,
            action="integration_registered",
            data=self._integration_audit_data(integration),
        )
        return integration

    async def register_shop(
        self,
        shop: BusinessShop,
        *,
        actor_id: str,
        request_id: str,
    ) -> BusinessShop:
        actor, request = self._identity(actor_id, request_id)
        if await self.registry.get_business(shop.business_id) is None:
            raise OperatorControlPlaneError(f"unknown business {shop.business_id!r}")
        await self._requested(
            business_id=shop.business_id,
            actor_id=actor,
            request_id=request,
            action="shop_register",
            data={"shop_id": shop.shop_id},
        )
        await self.configuration.register_shop(shop)
        await self._completed(
            business_id=shop.business_id,
            actor_id=actor,
            request_id=request,
            action="shop_registered",
            data={
                "shop_id": shop.shop_id,
                "status": shop.status,
                "is_primary": shop.is_primary,
                "location_configured": bool(shop.location),
                "hours_status": shop.hours_status,
            },
        )
        return shop

    async def set_capability_enabled(
        self,
        business_id: str,
        capability_id: str,
        *,
        enabled: bool,
        config: dict[str, object] | None,
        actor_id: str,
        request_id: str,
    ) -> BusinessProfile:
        actor, request = self._identity(actor_id, request_id)
        if capability_id in PLATFORM_CAPABILITY_IDS:
            raise OperatorControlPlaneError(
                "marketplace is a platform capability and cannot be assigned to a business"
            )
        if not self.catalogue.contains(capability_id):
            raise OperatorControlPlaneError(f"unknown capability {capability_id!r}")
        await self._requested(
            business_id=business_id,
            actor_id=actor,
            request_id=request,
            action="capability_change",
            data={"capability_id": capability_id, "enabled": enabled},
        )
        try:
            updated = await self.configuration.set_capability_enabled(
                business_id,
                capability_id,
                enabled=enabled,
                config=config,
            )
        except RuntimeProfileError as error:
            raise OperatorControlPlaneError(str(error)) from error
        await self._completed(
            business_id=business_id,
            actor_id=actor,
            request_id=request,
            action="capability_changed",
            data={
                "capability_id": capability_id,
                "enabled": enabled,
                "runtime_revision": updated.runtime_revision,
            },
        )
        return updated

    async def set_business_enabled(
        self,
        business_id: str,
        *,
        enabled: bool,
        actor_id: str,
        request_id: str,
    ) -> BusinessProfile:
        actor, request = self._identity(actor_id, request_id)
        await self._requested(
            business_id=business_id,
            actor_id=actor,
            request_id=request,
            action="business_enabled_change",
            data={"enabled": enabled},
        )
        try:
            updated = await self.configuration.set_business_enabled(
                business_id,
                enabled=enabled,
            )
        except RuntimeProfileError as error:
            raise OperatorControlPlaneError(str(error)) from error
        await self._completed(
            business_id=business_id,
            actor_id=actor,
            request_id=request,
            action="business_enabled_changed",
            data={"enabled": updated.enabled, "runtime_revision": updated.runtime_revision},
        )
        return updated

    async def update_integration(
        self,
        business_id: str,
        integration_id: str,
        *,
        base_url: str | None = None,
        auth_reference: str | None = None,
        enabled: bool | None = None,
        status: str | None = None,
        capabilities: frozenset[str] | None = None,
        config: dict[str, object] | None = None,
        actor_id: str,
        request_id: str,
    ) -> BusinessIntegration:
        actor, request = self._identity(actor_id, request_id)
        current = self._find_integration(
            await self.registry.list_integrations(business_id),
            integration_id,
        )
        if current is None:
            raise OperatorControlPlaneError(f"unknown integration {integration_id!r}")
        if capabilities is not None:
            unknown = sorted(item for item in capabilities if not self.catalogue.contains(item))
            if unknown:
                raise OperatorControlPlaneError(
                    f"unknown integration capabilities: {', '.join(unknown)}"
                )
        changes = {
            "endpoint_changed": base_url is not None and base_url != current.base_url,
            "auth_reference_changed": (
                auth_reference is not None and auth_reference != current.auth_reference
            ),
            "enabled_changed": enabled is not None and enabled != current.enabled,
            "status_changed": status is not None and status != current.status,
            "capabilities_changed": capabilities is not None and capabilities != current.capabilities,
            "config_changed": config is not None and dict(config) != dict(current.config),
        }
        updated = replace(
            current,
            base_url=current.base_url if base_url is None else base_url,
            auth_reference=(
                current.auth_reference if auth_reference is None else auth_reference
            ),
            enabled=current.enabled if enabled is None else enabled,
            status=current.status if status is None else status,
            capabilities=current.capabilities if capabilities is None else capabilities,
            config=(
                current.config
                if config is None
                else MappingProxyType(dict(config))
            ),
        )
        await self._requested(
            business_id=business_id,
            actor_id=actor,
            request_id=request,
            action="integration_update",
            data={"integration_id": integration_id, **changes},
        )
        await self.configuration.register_integration(updated)
        await self._completed(
            business_id=business_id,
            actor_id=actor,
            request_id=request,
            action="integration_updated",
            data={**self._integration_audit_data(updated), **changes},
        )
        return updated

    @staticmethod
    def _find_integration(
        integrations: tuple[BusinessIntegration, ...],
        integration_id: str,
    ) -> BusinessIntegration | None:
        return next(
            (item for item in integrations if item.integration_id == integration_id),
            None,
        )

    @staticmethod
    def _integration_audit_data(integration: BusinessIntegration) -> dict[str, Any]:
        # Intentionally excludes base_url, auth_reference and integration config.
        return {
            "integration_id": integration.integration_id,
            "provider": integration.provider,
            "adapter_type": integration.adapter_type,
            "api_version": integration.api_version,
            "status": integration.status,
            "enabled": integration.enabled,
            "capabilities": sorted(integration.capabilities),
            "endpoint_configured": bool(integration.base_url),
            "auth_reference_configured": bool(integration.auth_reference),
        }
