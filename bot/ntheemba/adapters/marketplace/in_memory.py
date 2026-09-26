"""In-memory Marketplace policy and handoff registry."""

from __future__ import annotations

from datetime import datetime

from ntheemba.domain.marketplace import MarketplaceBusinessListing, MarketplaceHandoff


class InMemoryMarketplaceRegistry:
    """Store Marketplace platform state for tests and local deterministic runtimes."""

    def __init__(
        self,
        *,
        listings: tuple[MarketplaceBusinessListing, ...] = (),
        handoffs: tuple[MarketplaceHandoff, ...] = (),
    ) -> None:
        self._listings = {item.business_id: item for item in listings}
        self._handoffs = {item.handoff_id: item for item in handoffs}

    async def get_listing(self, business_id: str) -> MarketplaceBusinessListing | None:
        return self._listings.get(business_id)

    async def list_listings(self) -> tuple[MarketplaceBusinessListing, ...]:
        return tuple(sorted(self._listings.values(), key=lambda item: item.business_id))

    async def save_listing(self, listing: MarketplaceBusinessListing) -> None:
        self._listings[listing.business_id] = listing

    async def get_handoff(self, handoff_id: str) -> MarketplaceHandoff | None:
        return self._handoffs.get(handoff_id)

    async def get_handoff_for_result(
        self, search_id: str, result_id: str
    ) -> MarketplaceHandoff | None:
        return next(
            (
                handoff
                for handoff in self._handoffs.values()
                if handoff.search_id == search_id and handoff.result_id == result_id
            ),
            None,
        )

    async def save_handoff(self, handoff: MarketplaceHandoff) -> None:
        existing = self._handoffs.get(handoff.handoff_id)
        if existing is not None and existing != handoff:
            raise ValueError("Marketplace handoff identity is immutable")
        selected = await self.get_handoff_for_result(handoff.search_id, handoff.result_id)
        if selected is not None and selected.handoff_id != handoff.handoff_id:
            raise ValueError("Marketplace result already has a handoff")
        self._handoffs[handoff.handoff_id] = handoff

    async def mark_handoff_consumed(
        self, handoff_id: str, *, consumed_at: datetime
    ) -> MarketplaceHandoff:
        handoff = self._handoffs.get(handoff_id)
        if handoff is None:
            raise LookupError("unknown Marketplace handoff")
        consumed = handoff.consume(at=consumed_at)
        self._handoffs[handoff_id] = consumed
        return consumed
