"""Ports for Ntheemba-owned Marketplace policy and handoff persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ntheemba.domain.marketplace import MarketplaceBusinessListing, MarketplaceHandoff


class MarketplaceRegistry(Protocol):
    """Read platform-owned Marketplace participation and handoff state."""

    async def get_listing(self, business_id: str) -> MarketplaceBusinessListing | None:
        """Return Marketplace participation for one business."""

    async def list_listings(self) -> tuple[MarketplaceBusinessListing, ...]:
        """Return all Marketplace participation records."""

    async def get_handoff(self, handoff_id: str) -> MarketplaceHandoff | None:
        """Return a persisted Marketplace handoff."""

    async def get_handoff_for_result(
        self, search_id: str, result_id: str
    ) -> MarketplaceHandoff | None:
        """Return the idempotent handoff for one Marketplace search result."""


class MutableMarketplaceRegistry(MarketplaceRegistry, Protocol):
    """Persist platform Marketplace policy and explicit selection handoffs."""

    async def save_listing(self, listing: MarketplaceBusinessListing) -> None:
        """Create or replace one business Marketplace listing."""

    async def save_handoff(self, handoff: MarketplaceHandoff) -> None:
        """Persist one explicit Marketplace selection handoff."""

    async def mark_handoff_consumed(
        self, handoff_id: str, *, consumed_at: datetime
    ) -> MarketplaceHandoff:
        """Atomically mark a ready handoff consumed and return the durable snapshot."""
