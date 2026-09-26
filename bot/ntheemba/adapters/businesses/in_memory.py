"""Deterministic in-memory business and unsupported-declaration adapters."""

from __future__ import annotations

from dataclasses import replace

from ntheemba.domain.business import (
    BusinessIntegration,
    BusinessProfile,
    BusinessShop,
    ChannelBinding,
    ChannelScope,
)
from ntheemba.ports.businesses import UnsupportedDeclarationObservation


class InMemoryBusinessRegistry:
    """Store business/channel configuration for tests and developer tools."""

    def __init__(
        self,
        *,
        businesses: tuple[BusinessProfile, ...] = (),
        channels: tuple[ChannelBinding, ...] = (),
        integrations: tuple[BusinessIntegration, ...] = (),
        shops: tuple[BusinessShop, ...] = (),
    ) -> None:
        self._businesses = {business.business_id: business for business in businesses}
        self._channels = {channel.channel_instance_id: channel for channel in channels}
        self._integrations: dict[str, list[BusinessIntegration]] = {}
        self._shops: dict[str, dict[str, BusinessShop]] = {}
        for channel in channels:
            if (
                channel.scope is ChannelScope.BUSINESS
                and channel.business_id not in self._businesses
            ):
                raise ValueError(
                    f"channel {channel.channel_instance_id!r} references unknown business "
                    f"{channel.business_id!r}"
                )
        identities = [channel.exact_identity for channel in channels]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate external channel identity")
        for integration in integrations:
            if integration.business_id not in self._businesses:
                raise ValueError(
                    f"integration {integration.integration_id!r} references unknown business "
                    f"{integration.business_id!r}"
                )
            self._integrations.setdefault(integration.business_id, []).append(integration)
        for shop in shops:
            if shop.business_id not in self._businesses:
                raise ValueError(f"shop {shop.shop_id!r} references unknown business {shop.business_id!r}")
            self._shops.setdefault(shop.business_id, {})[shop.shop_id] = shop

    async def get_business(self, business_id: str) -> BusinessProfile | None:
        return self._businesses.get(business_id)

    async def get_channel(self, channel_instance_id: str) -> ChannelBinding | None:
        return self._channels.get(channel_instance_id)

    async def get_channel_by_identity(
        self, provider: str, external_session_id: str, recipient_identifier: str
    ) -> ChannelBinding | None:
        identity = (provider, external_session_id, recipient_identifier)
        matches = [
            channel
            for channel in self._channels.values()
            if channel.exact_identity == identity
        ]
        if len(matches) > 1:
            raise ValueError("duplicate external channel identity")
        return matches[0] if matches else None

    async def list_businesses(self) -> tuple[BusinessProfile, ...]:
        return tuple(sorted(self._businesses.values(), key=lambda item: item.business_id))

    async def list_channels(self) -> tuple[ChannelBinding, ...]:
        return tuple(sorted(self._channels.values(), key=lambda item: item.channel_instance_id))

    async def list_integrations(self, business_id: str) -> tuple[BusinessIntegration, ...]:
        return tuple(
            sorted(
                self._integrations.get(business_id, ()),
                key=lambda item: item.integration_id,
            )
        )

    async def list_shops(self, business_id: str) -> tuple[BusinessShop, ...]:
        return tuple(sorted(self._shops.get(business_id, {}).values(), key=lambda item: item.shop_id))

    async def register_business(self, business: BusinessProfile) -> None:
        self._businesses[business.business_id] = business

    async def register_channel(self, channel: ChannelBinding) -> None:
        if (
            channel.scope is ChannelScope.BUSINESS
            and channel.business_id not in self._businesses
        ):
            raise ValueError(f"unknown business {channel.business_id!r}")
        existing = self._channels.get(channel.channel_instance_id)
        if existing is not None:
            if (
                existing.scope != channel.scope
                or existing.business_id != channel.business_id
            ):
                raise ValueError(
                    f"channel {channel.channel_instance_id!r} ownership is immutable"
                )
        for other in self._channels.values():
            if (
                other.channel_instance_id != channel.channel_instance_id
                and other.exact_identity == channel.exact_identity
            ):
                raise ValueError("external channel identity is already registered")
        if channel.is_primary:
            for key, other in list(self._channels.items()):
                same_scope = other.scope == channel.scope
                same_owner = (
                    channel.scope is ChannelScope.PLATFORM
                    or other.business_id == channel.business_id
                )
                if (
                    same_scope
                    and same_owner
                    and other.role == channel.role
                    and other.is_primary
                    and key != channel.channel_instance_id
                ):
                    self._channels[key] = replace(other, is_primary=False)
        self._channels[channel.channel_instance_id] = channel

    async def register_integration(self, integration: BusinessIntegration) -> None:
        if integration.business_id not in self._businesses:
            raise ValueError(f"unknown business {integration.business_id!r}")
        for business_id, values in self._integrations.items():
            if business_id != integration.business_id and any(
                item.integration_id == integration.integration_id for item in values
            ):
                raise ValueError(
                    f"integration {integration.integration_id!r} belongs to {business_id!r}"
                )
        current = [
            item
            for item in self._integrations.get(integration.business_id, [])
            if item.integration_id != integration.integration_id
        ]
        current.append(integration)
        self._integrations[integration.business_id] = current

    async def register_shop(self, shop: BusinessShop) -> None:
        if shop.business_id not in self._businesses:
            raise ValueError(f"unknown business {shop.business_id!r}")
        shops = self._shops.setdefault(shop.business_id, {})
        if shop.is_primary:
            for shop_id, current in list(shops.items()):
                if shop_id != shop.shop_id and current.is_primary:
                    shops[shop_id] = replace(current, is_primary=False)
        shops[shop.shop_id] = shop


class InMemoryRuntimeProfileCache:
    """Revision-keyed runtime profile cache for tests and local development."""

    def __init__(self) -> None:
        self._values: dict[tuple[str, str, int], str] = {}

    async def get(
        self,
        business_id: str,
        channel_instance_id: str,
        runtime_revision: int,
    ) -> str | None:
        return self._values.get((business_id, channel_instance_id, runtime_revision))

    async def set(
        self,
        business_id: str,
        channel_instance_id: str,
        runtime_revision: int,
        payload: str,
        *,
        ttl_seconds: int,
    ) -> None:
        del ttl_seconds
        self._values[(business_id, channel_instance_id, runtime_revision)] = payload

    async def invalidate(self, business_id: str) -> None:
        for key in list(self._values):
            if key[0] == business_id:
                del self._values[key]


class InMemoryUnsupportedDeclarationSink:
    """Collect unsupported declarations without changing runtime capabilities."""

    def __init__(self) -> None:
        self._observations: list[UnsupportedDeclarationObservation] = []

    async def record(self, observation: UnsupportedDeclarationObservation) -> None:
        identity = (
            observation.kind,
            observation.value,
            observation.business_id,
            observation.adapter_type,
        )
        existing = {
            (item.kind, item.value, item.business_id, item.adapter_type)
            for item in self._observations
        }
        if identity not in existing:
            self._observations.append(observation)

    async def list_observations(self) -> tuple[UnsupportedDeclarationObservation, ...]:
        return tuple(self._observations)
