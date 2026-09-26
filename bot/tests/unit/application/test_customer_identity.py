"""Tests for consent-aware customer recognition."""

from __future__ import annotations

import pytest

from ntheemba.application.customer_identity import (
    CustomerIdentityService,
    CustomerMemoryService,
    normalize_phone_number,
)
from ntheemba.domain.customer import ConsentType, QuestionOutcome
from ntheemba.infrastructure.memory.customers import MemoryCustomerRepository


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0971 234 567", "+260971234567"),
        ("+260 971 234 567", "+260971234567"),
        ("260971234567", "+260971234567"),
        ("00260971234567", "+260971234567"),
        ("971234567", "+260971234567"),
    ],
)
def test_zambian_phone_normalization(raw: str, expected: str) -> None:
    assert normalize_phone_number(raw) == expected


def test_phone_normalization_rejects_short_values() -> None:
    with pytest.raises(ValueError):
        normalize_phone_number("123")


async def test_new_customer_is_not_silently_shared_across_businesses() -> None:
    repository = MemoryCustomerRepository()
    service = CustomerIdentityService(repository)

    recognition = await service.recognize(
        business_id="harvest",
        phone_number="0971234567",
        suggested_name="WhatsApp James",
    )

    assert recognition.recognised_across_businesses is False
    assert recognition.saved_checkout_allowed is False
    assert recognition.display_name == "WhatsApp James"


async def test_customer_can_opt_in_to_cross_business_recognition() -> None:
    repository = MemoryCustomerRepository()
    service = CustomerIdentityService(repository)
    first = await service.recognize(
        business_id="harvest",
        phone_number="0971234567",
    )
    named = await service.remember_name(
        customer=first.customer,
        relationship=first.business_customer,
        name="James",
        share_across_businesses=True,
    )

    second = await service.recognize(
        business_id="serahs-glow-lounge",
        phone_number="+260971234567",
    )

    assert named.display_name == "James"
    assert second.recognised_across_businesses is True
    assert second.display_name == "James"
    assert second.business_customer.business_id == "serahs-glow-lounge"


async def test_business_private_name_does_not_leak_to_another_business() -> None:
    repository = MemoryCustomerRepository()
    service = CustomerIdentityService(repository)
    first = await service.recognize(
        business_id="harvest",
        phone_number="0971234567",
    )
    await service.remember_name(
        customer=first.customer,
        relationship=first.business_customer,
        name="Mr Chisulo",
        share_across_businesses=False,
    )

    second = await service.recognize(
        business_id="salon",
        phone_number="0971234567",
    )

    assert second.display_name is None
    assert second.should_ask_name is True


async def test_saved_checkout_requires_separate_consent() -> None:
    repository = MemoryCustomerRepository()
    service = CustomerIdentityService(repository)
    first = await service.recognize(
        business_id="harvest",
        phone_number="0971234567",
    )
    await service.set_consent(
        customer_id=first.customer.customer_id,
        consent_type=ConsentType.SAVED_CHECKOUT_DETAILS,
        granted=True,
        source="checkout_prompt",
    )

    returning = await service.recognize(
        business_id="harvest",
        phone_number="0971234567",
    )

    assert returning.saved_checkout_allowed is True


async def test_platform_and_business_addresses_are_scope_filtered() -> None:
    repository = MemoryCustomerRepository()
    service = CustomerIdentityService(repository)
    customer = await service.recognize(
        business_id="harvest",
        phone_number="0971234567",
    )
    await service.save_address(
        customer_id=customer.customer.customer_id,
        label="Home",
        location_text="Mufulira Central",
        business_id=None,
        is_default=True,
    )
    await service.save_address(
        customer_id=customer.customer.customer_id,
        label="Harvest delivery point",
        location_text="Shop entrance",
        business_id="harvest",
    )

    harvest = await repository.list_addresses(
        customer.customer.customer_id,
        business_id="harvest",
    )
    salon = await repository.list_addresses(
        customer.customer.customer_id,
        business_id="salon",
    )

    assert {item.label for item in harvest} == {"Home", "Harvest delivery point"}
    assert {item.label for item in salon} == {"Home"}


async def test_question_and_summary_memory_remains_business_scoped() -> None:
    repository = MemoryCustomerRepository()
    memory = CustomerMemoryService(repository)

    await memory.record_summary(
        conversation_id="CONV-1",
        business_id="harvest",
        customer_id="CUST-1",
        intent="faq",
        outcome="answered",
        topic="delivery",
    )
    await memory.record_question(
        business_id="harvest",
        customer_id="CUST-1",
        conversation_id="CONV-1",
        topic="delivery area",
        question_text="Do you deliver to Kantanshi?",
        outcome=QuestionOutcome.ANSWERED,
    )

    assert repository.summaries[0].business_id == "harvest"
    assert repository.questions[0].topic == "delivery area"


async def test_checkout_context_requires_consent_and_never_loads_other_business_data() -> None:
    repository = MemoryCustomerRepository()
    service = CustomerIdentityService(repository)
    recognition = await service.recognize(
        business_id="harvest",
        phone_number="0971234567",
    )
    await service.save_address(
        customer_id=recognition.customer.customer_id,
        label="Salon private",
        location_text="Salon-specific pickup",
        business_id="salon",
    )
    await service.save_address(
        customer_id=recognition.customer.customer_id,
        label="Home",
        location_text="Mufulira Central",
        business_id=None,
    )

    without_consent = await service.load_checkout_context(
        recognition,
        business_id="harvest",
    )
    assert without_consent.addresses == ()

    await service.set_consent(
        customer_id=recognition.customer.customer_id,
        consent_type=ConsentType.SAVED_CHECKOUT_DETAILS,
        granted=True,
        source="checkout_prompt",
    )
    returning = await service.recognize(
        business_id="harvest",
        phone_number="0971234567",
    )
    context = await service.load_checkout_context(returning, business_id="harvest")

    assert {item.label for item in context.addresses} == {"Home"}


async def test_customer_memory_can_retain_messages_separately_from_summaries() -> None:
    repository = MemoryCustomerRepository()
    memory = CustomerMemoryService(repository)

    message = await memory.record_message(
        message_id="MSG-1",
        conversation_id="CONV-1",
        business_id="harvest",
        customer_id="CUST-1",
        sender_type="customer",
        message_text="Do you deliver?",
    )

    assert message.sender_type == "customer"
    assert repository.messages == [message]


async def test_business_private_checkout_context_does_not_require_platform_consent() -> None:
    repository = MemoryCustomerRepository()
    service = CustomerIdentityService(repository)
    recognition = await service.recognize(
        business_id="harvest",
        phone_number="0971234567",
    )
    await service.save_address(
        customer_id=recognition.customer.customer_id,
        label="Harvest delivery point",
        location_text="Mufulira Central",
        business_id="harvest",
        is_default=True,
    )
    await service.save_address(
        customer_id=recognition.customer.customer_id,
        label="Platform home",
        location_text="Kitwe",
        business_id=None,
    )

    context = await service.load_checkout_context(recognition, business_id="harvest")

    assert [item.label for item in context.addresses] == ["Harvest delivery point"]
