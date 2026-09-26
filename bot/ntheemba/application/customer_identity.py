"""Privacy-aware customer recognition and durable memory services."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from ntheemba.domain.customer import (
    BusinessCustomer,
    ConsentType,
    ConversationMessage,
    ConversationSummary,
    Customer,
    CustomerAddress,
    CustomerCheckoutContext,
    CustomerConsent,
    CustomerPreference,
    CustomerQuestion,
    CustomerRecognition,
    CustomerWorkflowContext,
    QuestionOutcome,
)
from ntheemba.ports.customers import CustomerRepository

_PHONE_CLEANER = re.compile(r"[^0-9+]")


def normalize_phone_number(raw: str, *, default_country_code: str = "+260") -> str:
    """Normalize a customer phone number into a conservative E.164 representation."""

    cleaned = _PHONE_CLEANER.sub("", raw.strip())
    if cleaned.startswith("00"):
        cleaned = f"+{cleaned[2:]}"
    elif cleaned.startswith("+"):
        pass
    elif cleaned.startswith(default_country_code[1:]):
        cleaned = f"+{cleaned}"
    elif cleaned.startswith("0"):
        cleaned = f"{default_country_code}{cleaned[1:]}"
    else:
        cleaned = f"{default_country_code}{cleaned}"
    digits = cleaned[1:] if cleaned.startswith("+") else cleaned
    if not digits.isdigit() or not 8 <= len(digits) <= 15:
        raise ValueError("phone number could not be normalized to E.164")
    return f"+{digits}"


class CustomerIdentityService:
    """Resolve platform identity without exposing another business's private data."""

    def __init__(
        self,
        repository: CustomerRepository,
        *,
        default_country_code: str = "+260",
        cross_business_recognition_enabled: bool = True,
    ) -> None:
        self.repository = repository
        self.default_country_code = default_country_code
        self.cross_business_recognition_enabled = cross_business_recognition_enabled

    async def recognize(
        self,
        *,
        business_id: str,
        phone_number: str,
        suggested_name: str | None = None,
        preferred_language: str | None = None,
    ) -> CustomerRecognition:
        now = datetime.now(UTC)
        phone_e164 = normalize_phone_number(
            phone_number,
            default_country_code=self.default_country_code,
        )
        customer = await self.repository.find_customer_by_phone(phone_e164)
        was_existing = customer is not None
        if customer is None:
            customer = Customer.create(
                phone_e164,
                display_name=None,
                preferred_language=preferred_language,
                now=now,
            )
        else:
            customer = replace(
                customer,
                last_seen_at=now,
                preferred_language=customer.preferred_language or preferred_language,
            )
        customer = await self.repository.save_customer(customer)

        relationship = await self.repository.get_business_customer(
            business_id,
            customer.customer_id,
        )
        is_new_relationship = relationship is None
        if relationship is None:
            relationship = BusinessCustomer.create(
                business_id,
                customer.customer_id,
                preferred_name=None,
                now=now,
            )
        else:
            relationship = replace(relationship, last_seen_at=now)
        relationship = await self.repository.save_business_customer(relationship)

        recognition_consent = await self.repository.get_consent(
            customer.customer_id,
            ConsentType.CROSS_BUSINESS_RECOGNITION,
        )
        checkout_consent = await self.repository.get_consent(
            customer.customer_id,
            ConsentType.SAVED_CHECKOUT_DETAILS,
        )
        recognised_across = bool(
            self.cross_business_recognition_enabled
            and was_existing
            and is_new_relationship
            and recognition_consent is not None
            and recognition_consent.granted
        )
        platform_name_allowed = bool(
            relationship.preferred_name
            or not is_new_relationship
            or recognised_across
        )
        display_name = relationship.preferred_name
        if display_name is None and platform_name_allowed:
            display_name = customer.platform_display_name
        if display_name is None and not was_existing and suggested_name:
            display_name = suggested_name.strip() or None

        return CustomerRecognition(
            customer=customer,
            business_customer=relationship,
            display_name=display_name,
            recognised_across_businesses=recognised_across,
            saved_checkout_allowed=bool(checkout_consent and checkout_consent.granted),
            should_ask_name=display_name is None,
        )

    async def remember_name(
        self,
        *,
        customer: Customer,
        relationship: BusinessCustomer,
        name: str,
        share_across_businesses: bool,
    ) -> CustomerRecognition:
        cleaned = name.strip()
        if len(cleaned) < 2:
            raise ValueError("customer name must contain at least two characters")
        updated_relationship = replace(relationship, preferred_name=cleaned)
        updated_relationship = await self.repository.save_business_customer(updated_relationship)
        updated_customer = customer
        if share_across_businesses:
            updated_customer = replace(customer, platform_display_name=cleaned)
            updated_customer = await self.repository.save_customer(updated_customer)
            await self.set_consent(
                customer_id=customer.customer_id,
                consent_type=ConsentType.CROSS_BUSINESS_RECOGNITION,
                granted=True,
                source="customer_name_confirmation",
            )
        checkout = await self.repository.get_consent(
            customer.customer_id,
            ConsentType.SAVED_CHECKOUT_DETAILS,
        )
        return CustomerRecognition(
            customer=updated_customer,
            business_customer=updated_relationship,
            display_name=cleaned,
            recognised_across_businesses=share_across_businesses,
            saved_checkout_allowed=bool(checkout and checkout.granted),
            should_ask_name=False,
        )

    async def set_consent(
        self,
        *,
        customer_id: str,
        consent_type: ConsentType,
        granted: bool,
        source: str,
    ) -> CustomerConsent:
        consent = CustomerConsent(
            customer_id=customer_id,
            consent_type=consent_type,
            granted=granted,
            source=source,
        )
        return await self.repository.save_consent(consent)

    async def load_checkout_context(
        self,
        recognition: CustomerRecognition,
        *,
        business_id: str,
    ) -> CustomerCheckoutContext:
        addresses = await self.repository.list_addresses(
            recognition.customer.customer_id,
            business_id=business_id,
        )
        preferences = await self.repository.list_preferences(
            recognition.customer.customer_id,
            business_id=business_id,
        )
        allowed_addresses = tuple(
            item
            for item in addresses
            if item.business_id == business_id
            or (item.business_id is None and recognition.saved_checkout_allowed)
        )
        allowed_preferences = tuple(
            item
            for item in preferences
            if item.business_id == business_id
            or (item.business_id is None and recognition.saved_checkout_allowed)
        )
        return CustomerCheckoutContext(allowed_addresses, allowed_preferences)

    async def workflow_context(
        self,
        recognition: CustomerRecognition,
        *,
        business_id: str,
    ) -> CustomerWorkflowContext:
        """Build the privacy-filtered checkout context supplied to workflows."""

        checkout = await self.load_checkout_context(recognition, business_id=business_id)
        default_address = next(
            (item for item in checkout.addresses if item.is_default),
            checkout.addresses[0] if checkout.addresses else None,
        )
        return CustomerWorkflowContext(
            platform_customer_id=recognition.customer.customer_id,
            phone_e164=recognition.customer.phone_e164,
            display_name=recognition.display_name,
            recognised_across_businesses=recognition.recognised_across_businesses,
            platform_checkout_allowed=recognition.saved_checkout_allowed,
            default_delivery_location=(
                default_address.location_text if default_address is not None else None
            ),
        )

    async def save_address(
        self,
        *,
        customer_id: str,
        label: str,
        location_text: str,
        business_id: str | None,
        is_default: bool = False,
    ) -> CustomerAddress:
        address = CustomerAddress(
            address_id=f"ADDR-{uuid4()}",
            customer_id=customer_id,
            business_id=business_id,
            label=label,
            location_text=location_text,
            is_default=is_default,
        )
        return await self.repository.save_address(address)

    async def save_preference(
        self,
        *,
        customer_id: str,
        key: str,
        value: dict[str, object],
        business_id: str | None,
        source: str = "customer",
    ) -> CustomerPreference:
        preference = CustomerPreference(
            preference_id=f"PREF-{uuid4()}",
            customer_id=customer_id,
            business_id=business_id,
            key=key,
            value=value,
            source=source,
        )
        return await self.repository.save_preference(preference)


class CustomerMemoryService:
    """Persist compact summaries and business-private question analytics."""

    def __init__(self, repository: CustomerRepository) -> None:
        self.repository = repository

    async def message_retention_allowed(self, customer_id: str) -> bool:
        consent = await self.repository.get_consent(
            customer_id,
            ConsentType.CONVERSATION_RETENTION,
        )
        return bool(consent and consent.granted)

    async def record_message(
        self,
        *,
        message_id: str,
        conversation_id: str,
        business_id: str,
        customer_id: str,
        sender_type: str,
        message_text: str,
    ) -> ConversationMessage:
        record = ConversationMessage(
            message_id=message_id,
            conversation_id=conversation_id,
            business_id=business_id,
            customer_id=customer_id,
            sender_type=sender_type,
            message_text=message_text,
        )
        await self.repository.record_message(record)
        return record

    async def record_summary(
        self,
        *,
        conversation_id: str,
        business_id: str,
        customer_id: str,
        intent: str,
        outcome: str,
        topic: str | None = None,
        follow_up_required: bool = False,
        summary: dict[str, object] | None = None,
    ) -> ConversationSummary:
        record = ConversationSummary(
            summary_id=f"SUMMARY-{uuid4()}",
            conversation_id=conversation_id,
            business_id=business_id,
            customer_id=customer_id,
            intent=intent,
            outcome=outcome,
            topic=topic,
            follow_up_required=follow_up_required,
            summary=summary or {},
        )
        await self.repository.record_conversation_summary(record)
        return record

    async def record_question(
        self,
        *,
        business_id: str,
        customer_id: str,
        conversation_id: str,
        topic: str,
        question_text: str,
        outcome: QuestionOutcome,
        required_handover: bool = False,
    ) -> CustomerQuestion:
        record = CustomerQuestion(
            question_id=f"QUESTION-{uuid4()}",
            business_id=business_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            topic=topic,
            question_text=question_text,
            outcome=outcome,
            required_handover=required_handover,
        )
        await self.repository.record_question(record)
        return record
