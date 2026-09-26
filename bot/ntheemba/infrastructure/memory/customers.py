"""Tenant-safe in-memory customer repository."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import replace

from ntheemba.domain.customer import (
    BusinessCustomer,
    ConversationMessage,
    ConversationSummary,
    Customer,
    CustomerAddress,
    CustomerConsent,
    CustomerPreference,
    CustomerQuestion,
    ConsentType,
)
from ntheemba.ports.customers import CustomerRepository


class MemoryCustomerRepository(CustomerRepository):
    def __init__(self) -> None:
        self.customers: dict[str, Customer] = {}
        self.phone_index: dict[str, str] = {}
        self.business_customers: dict[tuple[str, str], BusinessCustomer] = {}
        self.consents: dict[tuple[str, ConsentType], CustomerConsent] = {}
        self.addresses: dict[str, CustomerAddress] = {}
        self.preferences: dict[str, CustomerPreference] = {}
        self.messages: list[ConversationMessage] = []
        self.summaries: list[ConversationSummary] = []
        self.questions: list[CustomerQuestion] = []
        self._guard = asyncio.Lock()

    async def find_customer_by_phone(self, phone_e164: str) -> Customer | None:
        async with self._guard:
            customer_id = self.phone_index.get(phone_e164)
            return self.customers.get(customer_id) if customer_id is not None else None

    async def save_customer(self, customer: Customer) -> Customer:
        async with self._guard:
            existing_id = self.phone_index.get(customer.phone_e164)
            if existing_id is not None and existing_id != customer.customer_id:
                raise ValueError("phone number is already assigned to another customer")
            self.customers[customer.customer_id] = customer
            self.phone_index[customer.phone_e164] = customer.customer_id
            return customer

    async def get_business_customer(
        self,
        business_id: str,
        customer_id: str,
    ) -> BusinessCustomer | None:
        async with self._guard:
            return self.business_customers.get((business_id, customer_id))

    async def save_business_customer(
        self,
        business_customer: BusinessCustomer,
    ) -> BusinessCustomer:
        async with self._guard:
            key = (business_customer.business_id, business_customer.customer_id)
            self.business_customers[key] = business_customer
            return business_customer

    async def get_consent(
        self,
        customer_id: str,
        consent_type: ConsentType,
    ) -> CustomerConsent | None:
        async with self._guard:
            return self.consents.get((customer_id, consent_type))

    async def save_consent(self, consent: CustomerConsent) -> CustomerConsent:
        async with self._guard:
            self.consents[(consent.customer_id, consent.consent_type)] = consent
            return consent

    async def list_addresses(
        self,
        customer_id: str,
        *,
        business_id: str | None,
    ) -> Sequence[CustomerAddress]:
        async with self._guard:
            return tuple(
                address
                for address in self.addresses.values()
                if address.customer_id == customer_id
                and (address.business_id is None or address.business_id == business_id)
            )

    async def save_address(self, address: CustomerAddress) -> CustomerAddress:
        async with self._guard:
            if address.is_default:
                for address_id, existing in tuple(self.addresses.items()):
                    if (
                        existing.customer_id == address.customer_id
                        and existing.business_id == address.business_id
                        and existing.is_default
                    ):
                        self.addresses[address_id] = replace(existing, is_default=False)
            self.addresses[address.address_id] = address
            return address

    async def list_preferences(
        self,
        customer_id: str,
        *,
        business_id: str | None,
    ) -> Sequence[CustomerPreference]:
        async with self._guard:
            return tuple(
                preference
                for preference in self.preferences.values()
                if preference.customer_id == customer_id
                and (preference.business_id is None or preference.business_id == business_id)
            )

    async def save_preference(self, preference: CustomerPreference) -> CustomerPreference:
        async with self._guard:
            self.preferences[preference.preference_id] = preference
            return preference

    async def record_message(self, message: ConversationMessage) -> None:
        async with self._guard:
            self.messages.append(message)

    async def record_conversation_summary(self, summary: ConversationSummary) -> None:
        async with self._guard:
            self.summaries.append(summary)

    async def record_question(self, question: CustomerQuestion) -> None:
        async with self._guard:
            self.questions.append(question)

    async def list_conversation_summaries(
        self,
        business_id: str,
        customer_id: str,
        *,
        limit: int = 50,
    ) -> Sequence[ConversationSummary]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        async with self._guard:
            matches = [
                item
                for item in self.summaries
                if item.business_id == business_id and item.customer_id == customer_id
            ]
            return tuple(reversed(matches[-limit:]))

    async def list_questions(
        self,
        business_id: str,
        customer_id: str,
        *,
        limit: int = 50,
    ) -> Sequence[CustomerQuestion]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        async with self._guard:
            matches = [
                item
                for item in self.questions
                if item.business_id == business_id and item.customer_id == customer_id
            ]
            return tuple(reversed(matches[-limit:]))

    async def ping(self) -> bool:
        return True
