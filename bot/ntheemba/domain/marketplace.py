"""Platform-owned Marketplace participation, discovery, and handoff models."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import uuid4

from ntheemba.domain.business import (
    BusinessIntegration,
    BusinessProfile,
    ChannelRole,
    ChannelScope,
    ResolvedPlatformContext,
)
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.product_resolution import ProductQuery


def _utc_now() -> datetime:
    return datetime.now(UTC)


class MarketplaceListingStatus(StrEnum):
    """Platform policy state for one business's Marketplace participation."""

    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    REJECTED = "rejected"


class MarketplaceHandoffStatus(StrEnum):
    """Lifecycle for an explicit Marketplace-to-business handoff."""

    READY = "ready"
    CONSUMED = "consumed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class MarketplaceBusinessListing:
    """Marketplace eligibility owned by Ntheemba, separate from business capabilities."""

    business_id: str
    status: MarketplaceListingStatus = MarketplaceListingStatus.PENDING
    discoverable: bool = False
    province_id: str = ""
    district_id: str = ""
    town_id: str = ""
    area_text: str = ""
    metadata: MappingProxyType[str, Any] = MappingProxyType({})
    updated_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.business_id.strip():
            raise ValueError("business_id must not be empty")
        if self.updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")
        if self.discoverable and self.status is not MarketplaceListingStatus.ACTIVE:
            raise ValueError("only active Marketplace listings may be discoverable")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def eligible(self) -> bool:
        return self.status is MarketplaceListingStatus.ACTIVE and self.discoverable


@dataclass(frozen=True, slots=True)
class MarketplaceDiscoveryFilter:
    """Optional deterministic business-discovery filters."""

    province_id: str = ""
    district_id: str = ""
    town_id: str = ""
    area_text: str = ""


@dataclass(frozen=True, slots=True)
class MarketplaceProductOffer:
    """One trusted cross-business product offer produced by Marketplace discovery."""

    result_id: str
    business_id: str
    business_name: str
    business_product_id: str
    ncpc_product_id: str
    ncpc_variant_id: str
    name: str
    selling_price: Decimal
    currency: str
    available_quantity: int
    integration_id: str
    business_runtime_revision: int
    shop_id: str = ""
    score: float = 1.0

    def __post_init__(self) -> None:
        for name, value in {
            "result_id": self.result_id,
            "business_id": self.business_id,
            "business_name": self.business_name,
            "business_product_id": self.business_product_id,
            "ncpc_product_id": self.ncpc_product_id,
            "ncpc_variant_id": self.ncpc_variant_id,
            "name": self.name,
            "integration_id": self.integration_id,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.selling_price < 0:
            raise ValueError("selling_price must not be negative")
        if self.available_quantity <= 0:
            raise ValueError("Marketplace offers require positive availability")
        currency = self.currency.strip().upper()
        if len(currency) != 3:
            raise ValueError("currency must use a three-letter code")
        object.__setattr__(self, "currency", currency)
        if self.business_runtime_revision < 0:
            raise ValueError("business_runtime_revision must not be negative")
        if not 0 <= self.score <= 1:
            raise ValueError("score must be between zero and one")


@dataclass(frozen=True, slots=True)
class MarketplaceProductSearch:
    """Bounded Marketplace search snapshot used for explicit customer selection."""

    source_channel_id: str
    query: ProductQuery
    offers: tuple[MarketplaceProductOffer, ...] = ()
    unavailable_business_ids: tuple[str, ...] = ()
    search_id: str = field(default_factory=lambda: f"MPS-{uuid4()}")
    created_at: datetime = field(default_factory=_utc_now)
    expires_at: datetime = field(default_factory=lambda: _utc_now() + timedelta(minutes=15))

    def __post_init__(self) -> None:
        if not self.source_channel_id.strip() or not self.search_id.strip():
            raise ValueError("source_channel_id and search_id must not be empty")
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("Marketplace search timestamps must be timezone-aware")
        if self.expires_at <= self.created_at:
            raise ValueError("Marketplace search must expire after creation")
        result_ids = [offer.result_id for offer in self.offers]
        if len(set(result_ids)) != len(result_ids):
            raise ValueError("Marketplace result IDs must be unique")

    def is_expired(self, *, now: datetime | None = None) -> bool:
        moment = now or _utc_now()
        if moment.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return moment >= self.expires_at


@dataclass(frozen=True, slots=True)
class MarketplaceHandoff:
    """Persisted, audit-safe snapshot of an explicit Marketplace selection."""

    search_id: str
    result_id: str
    source_channel_id: str
    target_business_id: str
    business_product_id: str
    ncpc_product_id: str
    ncpc_variant_id: str
    product_name: str
    selling_price_snapshot: Decimal
    currency: str
    integration_id: str
    business_runtime_revision: int
    shop_id: str = ""
    status: MarketplaceHandoffStatus = MarketplaceHandoffStatus.READY
    handoff_id: str = field(default_factory=lambda: f"MPH-{uuid4()}")
    created_at: datetime = field(default_factory=_utc_now)
    consumed_at: datetime | None = None

    def __post_init__(self) -> None:
        for name, value in {
            "handoff_id": self.handoff_id,
            "search_id": self.search_id,
            "result_id": self.result_id,
            "source_channel_id": self.source_channel_id,
            "target_business_id": self.target_business_id,
            "business_product_id": self.business_product_id,
            "ncpc_product_id": self.ncpc_product_id,
            "ncpc_variant_id": self.ncpc_variant_id,
            "product_name": self.product_name,
            "integration_id": self.integration_id,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.selling_price_snapshot < 0:
            raise ValueError("selling_price_snapshot must not be negative")
        currency = self.currency.strip().upper()
        if len(currency) != 3:
            raise ValueError("currency must use a three-letter code")
        object.__setattr__(self, "currency", currency)
        if self.business_runtime_revision < 0:
            raise ValueError("business_runtime_revision must not be negative")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.consumed_at is not None and self.consumed_at.tzinfo is None:
            raise ValueError("consumed_at must be timezone-aware")
        if self.status is MarketplaceHandoffStatus.CONSUMED and self.consumed_at is None:
            raise ValueError("consumed handoffs require consumed_at")
        if self.status is MarketplaceHandoffStatus.READY and self.consumed_at is not None:
            raise ValueError("ready handoffs cannot have consumed_at")

    def consume(self, *, at: datetime | None = None) -> MarketplaceHandoff:
        """Return an idempotently consumed handoff snapshot."""

        if self.status is MarketplaceHandoffStatus.CANCELLED:
            raise ValueError("cancelled Marketplace handoffs cannot be consumed")
        if self.status is MarketplaceHandoffStatus.CONSUMED:
            return self
        moment = at or _utc_now()
        if moment.tzinfo is None:
            raise ValueError("consumption time must be timezone-aware")
        if moment < self.created_at:
            raise ValueError("consumption time cannot precede handoff creation")
        return replace(
            self,
            status=MarketplaceHandoffStatus.CONSUMED,
            consumed_at=moment,
        )


@dataclass(frozen=True, slots=True)
class MarketplaceBusinessHandoffContext:
    """Trusted business-bound context reached only after explicit Marketplace selection.

    The source remains a platform channel.  This type intentionally does not inherit from
    ``ResolvedBusinessContext`` because a platform channel must never masquerade as a
    tenant-owned business channel.
    """

    source_platform_context: ResolvedPlatformContext
    business: BusinessProfile
    capabilities: frozenset[Capability]
    integrations: tuple[BusinessIntegration, ...]
    handoff: MarketplaceHandoff

    def __post_init__(self) -> None:
        if self.source_platform_context.channel.scope is not ChannelScope.PLATFORM:
            raise ValueError("Marketplace handoff requires a platform source context")
        if self.source_platform_context.role is not ChannelRole.MARKETPLACE:
            raise ValueError("Marketplace handoff requires the Marketplace platform role")
        if self.business.business_id != self.handoff.target_business_id:
            raise ValueError("handoff target business does not match business context")
        if Capability.PRODUCT_CATALOGUE not in self.capabilities:
            raise ValueError("Marketplace handoff target requires product catalogue capability")

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def integration_for(self, capability: Capability) -> BusinessIntegration | None:
        matches = tuple(
            integration
            for integration in self.integrations
            if integration.enabled
            and integration.status == "active"
            and capability.value in integration.capabilities
        )
        if len(matches) != 1:
            return None
        return matches[0]
