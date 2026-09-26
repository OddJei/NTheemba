"""Minimal platform-customer and TradeFlow-client bridge."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from ntheemba.domain.customer_memory import ConsentType
from ntheemba.domain.customers import BusinessClientLink, MinimalBusinessClient, PlatformCustomer
from ntheemba.ports.customers import CustomerDirectory
from ntheemba.ports.tradeflow import MinimalClientCreateRequest


class CustomerConsentReader(Protocol):
    """Read explicit customer permissions without exposing storage details."""

    async def is_allowed(
        self,
        customer_id: str,
        consent_type: ConsentType,
    ) -> bool: ...


class BusinessClientPort(Protocol):
    """Structural client capability implemented by eligible TradeFlow adapters."""

    async def find_client_by_phone(
        self,
        business_id: str,
        phone_e164: str,
    ) -> MinimalBusinessClient | None: ...

    async def create_minimal_client(
        self,
        business_id: str,
        request: MinimalClientCreateRequest,
        *,
        idempotency_key: str,
    ) -> MinimalBusinessClient: ...


class CustomerBridgeService:
    """Resolve identities and create only minimal tenant-specific links."""

    def __init__(
        self,
        *,
        customers: CustomerDirectory,
        clients: BusinessClientPort,
        consents: CustomerConsentReader | None = None,
    ) -> None:
        self.customers = customers
        self.clients = clients
        self.consents = consents

    async def resolve_platform_customer(self, phone_e164: str) -> PlatformCustomer:
        return await self.customers.resolve_by_phone(phone_e164)

    async def resolve_business_client(
        self,
        *,
        business_id: str,
        customer_id: str,
    ) -> BusinessClientLink | None:
        existing = await self.customers.get_business_link(business_id, customer_id)
        if existing is not None:
            return existing
        customer = await self.customers.get_customer(customer_id)
        if customer is None:
            raise LookupError(customer_id)
        client = await self.clients.find_client_by_phone(business_id, customer.phone_e164)
        if client is None:
            return None
        link = BusinessClientLink(
            business_id=business_id,
            customer_id=customer_id,
            external_client_id=client.client_id,
            business_display_name=client.display_name,
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        )
        return await self.customers.save_business_link(link)

    async def reusable_platform_name(self, customer_id: str) -> str:
        """Return a platform name only when cross-business reuse was allowed."""

        if self.consents is None or not await self.consents.is_allowed(
            customer_id,
            ConsentType.CROSS_BUSINESS_NAME,
        ):
            return ""
        customer = await self.customers.get_customer(customer_id)
        return "" if customer is None else customer.preferred_name

    async def ensure_business_client(
        self,
        *,
        business_id: str,
        customer_id: str,
        display_name: str,
        idempotency_key: str,
    ) -> BusinessClientLink:
        existing = await self.resolve_business_client(
            business_id=business_id,
            customer_id=customer_id,
        )
        if existing is not None:
            return existing
        customer = await self.customers.get_customer(customer_id)
        if customer is None:
            raise LookupError(customer_id)
        client = await self.clients.create_minimal_client(
            business_id,
            MinimalClientCreateRequest(
                display_name=display_name,
                phone_e164=customer.phone_e164,
            ),
            idempotency_key=idempotency_key,
        )
        if (
            not customer.preferred_name
            and self.consents is not None
            and await self.consents.is_allowed(
                customer_id,
                ConsentType.CROSS_BUSINESS_NAME,
            )
        ):
            await self.customers.update_preferred_name(customer_id, display_name)
        link = BusinessClientLink(
            business_id=business_id,
            customer_id=customer_id,
            external_client_id=client.client_id,
            business_display_name=client.display_name,
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        )
        return await self.customers.save_business_link(link)
