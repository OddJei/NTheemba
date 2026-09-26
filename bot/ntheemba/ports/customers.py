"""Ports for minimal platform customers and private business-client links."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from ntheemba.domain.customer import (
    BusinessCustomer,
    ConsentType,
    ConversationMessage,
    ConversationSummary,
    Customer,
    CustomerAddress,
    CustomerConsent,
    CustomerPreference,
    CustomerQuestion,
)
from ntheemba.domain.customers import BusinessClientLink, PlatformCustomer


class CustomerDirectory(Protocol):
    """Resolve minimal platform identities without exposing business history."""

    async def resolve_by_phone(self, phone_e164: str) -> PlatformCustomer:
        """Return or create one platform customer by normalised phone."""

    async def get_customer(self, customer_id: str) -> PlatformCustomer | None:
        """Return one platform customer."""

    async def update_preferred_name(
        self,
        customer_id: str,
        preferred_name: str,
    ) -> PlatformCustomer:
        """Update a reusable name after customer confirmation."""

    async def get_business_link(
        self,
        business_id: str,
        customer_id: str,
    ) -> BusinessClientLink | None:
        """Return one tenant-private client relationship."""

    async def save_business_link(self, link: BusinessClientLink) -> BusinessClientLink:
        """Save one tenant-private relationship."""


class CustomerRepository(Protocol):
    """Privacy-aware customer repository used by the legacy durable-memory service."""

    async def find_customer_by_phone(self, phone_e164: str) -> Customer | None:
        """Return one platform customer by phone number."""

    async def save_customer(self, customer: Customer) -> Customer:
        """Persist one platform customer."""

    async def get_business_customer(
        self,
        business_id: str,
        customer_id: str,
    ) -> BusinessCustomer | None:
        """Return the tenant-private relationship for one platform customer."""

    async def save_business_customer(
        self,
        business_customer: BusinessCustomer,
    ) -> BusinessCustomer:
        """Persist one tenant-private customer relationship."""

    async def get_consent(
        self,
        customer_id: str,
        consent_type: ConsentType,
    ) -> CustomerConsent | None:
        """Return one customer consent value."""

    async def save_consent(self, consent: CustomerConsent) -> CustomerConsent:
        """Persist one consent value."""

    async def list_addresses(
        self,
        customer_id: str,
        *,
        business_id: str | None,
    ) -> Sequence[CustomerAddress]:
        """Return platform and tenant-scoped addresses visible to a business."""

    async def save_address(self, address: CustomerAddress) -> CustomerAddress:
        """Persist one address."""

    async def list_preferences(
        self,
        customer_id: str,
        *,
        business_id: str | None,
    ) -> Sequence[CustomerPreference]:
        """Return platform and tenant-scoped preferences visible to a business."""

    async def save_preference(self, preference: CustomerPreference) -> CustomerPreference:
        """Persist one preference."""

    async def record_message(self, message: ConversationMessage) -> None:
        """Record one conversation message if retention is allowed."""

    async def record_conversation_summary(self, summary: ConversationSummary) -> None:
        """Record one compact conversation summary."""

    async def record_question(self, question: CustomerQuestion) -> None:
        """Record one business-scoped customer question."""

    async def list_conversation_summaries(
        self,
        business_id: str,
        customer_id: str,
        *,
        limit: int = 50,
    ) -> Sequence[ConversationSummary]:
        """Return recent business-scoped conversation summaries."""

    async def list_questions(
        self,
        business_id: str,
        customer_id: str,
        *,
        limit: int = 50,
    ) -> Sequence[CustomerQuestion]:
        """Return recent business-scoped customer questions."""

    async def ping(self) -> bool:
        """Return whether the repository is reachable."""
