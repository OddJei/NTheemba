"""Consent-scoped durable customer memory tests."""

from datetime import UTC, datetime

import pytest

from ntheemba.application.customer_memory import CustomerMemoryService
from ntheemba.application.service import ProcessMessageCommand
from ntheemba.application.workflow_router import WorkflowReply, WorkflowResult
from ntheemba.domain.customer_memory import ConsentType
from ntheemba.domain.enums import Flow, FulfilmentMethod, IntentType, MessageRole, Stage
from ntheemba.domain.intents import Intent
from ntheemba.domain.order_draft import OrderDraft
from ntheemba.domain.session import Session
from ntheemba.infrastructure.memory import MemoryCustomerMemoryRepository


def command() -> ProcessMessageCommand:
    return ProcessMessageCommand(
        business_id="harvest-big-shop",
        customer_id="CUST-1",
        message_id="MSG-1",
        text="Where are you located?",
        customer_phone="+260971234567",
        received_at=datetime(2026, 8, 2, 10, 0, tzinfo=UTC),
    )


def session(*, with_checkout: bool = False) -> Session:
    draft = None
    if with_checkout:
        draft = OrderDraft(
            fulfilment_method=FulfilmentMethod.DELIVERY,
            delivery_details="Mufulira Central near the post office",
        )
    return Session(
        conversation_id="CONV-1",
        business_id="harvest-big-shop",
        customer_id="CUST-1",
        flow=Flow.ORDER if with_checkout else Flow.INFORMATION,
        stage=Stage.ORDER_REVIEW if with_checkout else Stage.START,
        order_draft=draft,
    )


def faq_intent() -> Intent:
    return Intent(IntentType.FAQ, MessageRole.NEW_REQUEST, 1.0)


def result() -> WorkflowResult:
    return WorkflowResult(replies=(WorkflowReply.text_reply("We are in Mufulira."),))


@pytest.mark.asyncio
async def test_summary_is_stored_without_raw_message_consent() -> None:
    repository = MemoryCustomerMemoryRepository()
    service = CustomerMemoryService(repository)

    await service.record_success(
        command=command(),
        session=session(),
        intent=faq_intent(),
        result=result(),
        published_message_ids=("OUT-1",),
    )

    assert len(repository.summaries) == 1
    assert repository.messages == {}
    assert repository.questions == {}


@pytest.mark.asyncio
async def test_message_retention_consent_enables_raw_messages_and_questions() -> None:
    repository = MemoryCustomerMemoryRepository()
    service = CustomerMemoryService(repository)
    await service.set_consent(
        "CUST-1",
        ConsentType.MESSAGE_RETENTION,
        True,
        source="customer_chat",
    )

    await service.record_success(
        command=command(),
        session=session(),
        intent=faq_intent(),
        result=result(),
        published_message_ids=("OUT-1",),
    )

    assert set(repository.messages) == {"MSG-1", "OUT-1"}
    assert len(repository.questions) == 1


@pytest.mark.asyncio
async def test_saved_checkout_consent_is_required_for_business_address() -> None:
    repository = MemoryCustomerMemoryRepository()
    service = CustomerMemoryService(repository)

    await service.record_success(
        command=command(),
        session=session(with_checkout=True),
        intent=faq_intent(),
        result=result(),
        published_message_ids=("OUT-1",),
    )
    assert repository.addresses == {}

    await service.set_consent(
        "CUST-1",
        ConsentType.SAVED_CHECKOUT,
        True,
        source="checkout_confirmation",
    )
    await service.record_success(
        command=command(),
        session=session(with_checkout=True),
        intent=faq_intent(),
        result=result(),
        published_message_ids=("OUT-2",),
    )

    saved = tuple(repository.addresses.values())
    assert len(saved) == 1
    assert saved[0].business_id == "harvest-big-shop"
    assert saved[0].location_text.startswith("Mufulira Central")
