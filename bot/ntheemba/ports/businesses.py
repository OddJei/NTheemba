"""Ports for business/channel routing and unsupported declaration review."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from ntheemba.domain.business import BusinessShop, ChannelBinding, BusinessChannel, BusinessIntegration, BusinessProfile


class UnsupportedDeclarationKind(StrEnum):
    """Unsupported integration declarations Ntheemba records for review."""

    CAPABILITY = "capability"
    TRADEFLOW_OPERATION = "tradeflow_operation"


@dataclass(frozen=True, slots=True)
class UnsupportedDeclarationObservation:
    """Audit-safe observation of something an integration attempted to expose."""

    kind: UnsupportedDeclarationKind
    value: str
    business_id: str
    adapter_type: str
    observed_at: datetime
    source: str = "tradeflow"

    def __post_init__(self) -> None:
        for name, value in {
            "value": self.value,
            "business_id": self.business_id,
            "adapter_type": self.adapter_type,
            "source": self.source,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")

    @classmethod
    def now(
        cls,
        *,
        kind: UnsupportedDeclarationKind,
        value: str,
        business_id: str,
        adapter_type: str,
        source: str = "tradeflow",
    ) -> UnsupportedDeclarationObservation:
        """Create an observation at the current UTC time."""

        return cls(kind, value, business_id, adapter_type, datetime.now(UTC), source)


class BusinessRegistry(Protocol):
    """Read configured businesses and channels."""

    async def get_business(self, business_id: str) -> BusinessProfile | None:
        """Return a configured business."""

    async def get_channel(self, channel_instance_id: str) -> ChannelBinding | None:
        """Return one configured channel by stable internal identifier."""

    async def get_channel_by_identity(
        self, provider: str, external_session_id: str, recipient_identifier: str
    ) -> ChannelBinding | None:
        """Return one channel only when the exact external routing identity matches."""

    async def list_businesses(self) -> tuple[BusinessProfile, ...]:
        """Return configured businesses."""

    async def list_channels(self) -> tuple[ChannelBinding, ...]:
        """Return configured channels."""

    async def list_integrations(self, business_id: str) -> tuple[BusinessIntegration, ...]:
        """Return configured integrations for one business."""

    async def list_shops(self, business_id: str) -> tuple[BusinessShop, ...]:
        """Return the safe configured shop-routing projection for one business."""


class MutableBusinessRegistry(BusinessRegistry, Protocol):
    """Persist business runtime configuration changes."""

    async def register_business(self, business: BusinessProfile) -> None:
        """Create or update a business and its enabled capabilities."""

    async def register_channel(self, channel: ChannelBinding) -> None:
        """Create or update one business channel."""

    async def register_integration(self, integration: BusinessIntegration) -> None:
        """Create or update one business integration."""

    async def register_shop(self, shop: BusinessShop) -> None:
        """Create or update one tenant-bound shop projection."""


class RuntimeProfileCache(Protocol):
    """Cache compiled runtime profiles by business revision and channel."""

    async def get(
        self,
        business_id: str,
        channel_instance_id: str,
        runtime_revision: int,
    ) -> str | None:
        """Return a serialized compiled profile if present."""

    async def set(
        self,
        business_id: str,
        channel_instance_id: str,
        runtime_revision: int,
        payload: str,
        *,
        ttl_seconds: int,
    ) -> None:
        """Store one serialized compiled profile."""

    async def invalidate(self, business_id: str) -> None:
        """Remove cached profiles for a business after configuration changes."""


class UnsupportedDeclarationSink(Protocol):
    """Record unknown capability names and adapter operations for review."""

    async def record(self, observation: UnsupportedDeclarationObservation) -> None:
        """Persist one observation without enabling it."""

    async def list_observations(self) -> tuple[UnsupportedDeclarationObservation, ...]:
        """Return recorded observations for developer diagnostics."""
