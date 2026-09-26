"""In-memory Phase 12 customer memory implementation."""

from __future__ import annotations

from datetime import datetime

from ntheemba.domain.customer_memory import (
    ConversationMessage,
    ConversationSummary,
    CustomerAddress,
    CustomerConsent,
    CustomerPreference,
    CustomerQuestion,
    RetentionResult,
)


class MemoryCustomerMemoryRepository:
    def __init__(self) -> None:
        self.consents: dict[tuple[str, str], CustomerConsent] = {}
        self.addresses: dict[str, CustomerAddress] = {}
        self.preferences: dict[tuple[str, str | None, str], CustomerPreference] = {}
        self.messages: dict[str, ConversationMessage] = {}
        self.summaries: dict[str, ConversationSummary] = {}
        self.questions: dict[str, CustomerQuestion] = {}

    async def get_consent(self, customer_id: str, consent_type: str) -> CustomerConsent | None:
        return self.consents.get((customer_id, consent_type))

    async def save_consent(self, consent: CustomerConsent) -> CustomerConsent:
        self.consents[(consent.customer_id, consent.consent_type.value)] = consent
        return consent

    async def list_addresses(self, customer_id: str, *, business_id: str | None) -> tuple[CustomerAddress, ...]:
        values = [
            item for item in self.addresses.values()
            if item.customer_id == customer_id and (item.business_id is None or item.business_id == business_id)
        ]
        return tuple(sorted(values, key=lambda item: (not item.is_default, item.created_at)))

    async def save_address(self, address: CustomerAddress) -> CustomerAddress:
        if address.is_default:
            for key, current in list(self.addresses.items()):
                if current.customer_id == address.customer_id and current.business_id == address.business_id:
                    self.addresses[key] = CustomerAddress(
                        current.address_id, current.customer_id, current.label, current.location_text,
                        current.business_id, False, current.created_at,
                    )
        self.addresses[address.address_id] = address
        return address

    async def list_preferences(self, customer_id: str, *, business_id: str | None) -> tuple[CustomerPreference, ...]:
        return tuple(
            item for item in self.preferences.values()
            if item.customer_id == customer_id and (item.business_id is None or item.business_id == business_id)
        )

    async def save_preference(self, preference: CustomerPreference) -> CustomerPreference:
        self.preferences[(preference.customer_id, preference.business_id, preference.key)] = preference
        return preference

    async def record_message(self, message: ConversationMessage) -> None:
        self.messages.setdefault(message.message_id, message)

    async def record_summary(self, summary: ConversationSummary) -> None:
        self.summaries.setdefault(summary.summary_id, summary)

    async def record_question(self, question: CustomerQuestion) -> None:
        self.questions.setdefault(question.question_id, question)

    async def list_summaries(self, business_id: str, customer_id: str, *, limit: int = 50) -> tuple[ConversationSummary, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        values = [x for x in self.summaries.values() if x.business_id == business_id and x.customer_id == customer_id]
        return tuple(sorted(values, key=lambda x: x.created_at, reverse=True)[:limit])

    async def list_questions(self, business_id: str, customer_id: str, *, limit: int = 50) -> tuple[CustomerQuestion, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        values = [x for x in self.questions.values() if x.business_id == business_id and x.customer_id == customer_id]
        return tuple(sorted(values, key=lambda x: x.created_at, reverse=True)[:limit])

    async def delete_customer(self, customer_id: str) -> None:
        self.consents = {k: v for k, v in self.consents.items() if v.customer_id != customer_id}
        self.addresses = {k: v for k, v in self.addresses.items() if v.customer_id != customer_id}
        self.preferences = {k: v for k, v in self.preferences.items() if v.customer_id != customer_id}
        self.messages = {k: v for k, v in self.messages.items() if v.customer_id != customer_id}
        self.summaries = {k: v for k, v in self.summaries.items() if v.customer_id != customer_id}
        self.questions = {k: v for k, v in self.questions.items() if v.customer_id != customer_id}

    async def cleanup(self, *, message_cutoff: datetime, summary_cutoff: datetime, question_cutoff: datetime, unsupported_cutoff: datetime) -> RetentionResult:
        before = (len(self.messages), len(self.summaries), len(self.questions))
        self.messages = {k: v for k, v in self.messages.items() if v.created_at >= message_cutoff}
        self.summaries = {k: v for k, v in self.summaries.items() if v.created_at >= summary_cutoff}
        self.questions = {k: v for k, v in self.questions.items() if v.created_at >= question_cutoff}
        return RetentionResult(
            messages_deleted=before[0] - len(self.messages),
            summaries_deleted=before[1] - len(self.summaries),
            questions_deleted=before[2] - len(self.questions),
        )
