"""In-memory minimal customer directory for Phase 11 acceptance tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from ntheemba.domain.customers import (
    BusinessClientLink,
    PlatformCustomer,
    normalize_phone_e164,
)


class InMemoryCustomerDirectory:
    """Keep platform identity separate from tenant-private client links."""

    def __init__(self) -> None:
        self._customers: dict[str, PlatformCustomer] = {}
        self._customer_by_phone: dict[str, str] = {}
        self._links: dict[tuple[str, str], BusinessClientLink] = {}

    async def resolve_by_phone(self, phone_e164: str) -> PlatformCustomer:
        normalised = normalize_phone_e164(phone_e164)
        customer_id = self._customer_by_phone.get(normalised)
        now = datetime.now(UTC)
        if customer_id is None:
            customer = PlatformCustomer(
                customer_id=f"CUST-{uuid4()}",
                phone_e164=normalised,
                created_at=now,
                last_seen_at=now,
            )
            self._customers[customer.customer_id] = customer
            self._customer_by_phone[normalised] = customer.customer_id
            return customer
        current = self._customers[customer_id]
        updated = replace(current, last_seen_at=now)
        self._customers[customer_id] = updated
        return updated

    async def get_customer(self, customer_id: str) -> PlatformCustomer | None:
        return self._customers.get(customer_id)

    async def update_preferred_name(
        self,
        customer_id: str,
        preferred_name: str,
    ) -> PlatformCustomer:
        name = preferred_name.strip()
        if len(name) < 2:
            raise ValueError("preferred_name is invalid")
        current = self._customers[customer_id]
        updated = replace(current, preferred_name=name, last_seen_at=datetime.now(UTC))
        self._customers[customer_id] = updated
        return updated

    async def get_business_link(
        self,
        business_id: str,
        customer_id: str,
    ) -> BusinessClientLink | None:
        return self._links.get((business_id, customer_id))

    async def save_business_link(self, link: BusinessClientLink) -> BusinessClientLink:
        self._links[(link.business_id, link.customer_id)] = link
        return link
