"""Tests for rule-first and model-fallback interpretation."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.enums import (
    Flow,
    FulfilmentMethod,
    IntentType,
    MessageRole,
    RelativeSize,
    Stage,
)
from ntheemba.domain.intents import PendingQuestion
from ntheemba.domain.session import ConversationTurn, Session
from ntheemba.services.interpretation import (
    HybridInterpreter,
    allowed_actions_for_capabilities,
    build_model_context,
)


class StubModel:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    async def propose(
        self,
        text: str,
        context: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        self.calls.append((text, context))
        return self.payload


def _session(*, flow: Flow = Flow.IDLE, stage: Stage = Stage.START) -> Session:
    session = Session.create(
        "BUS-1",
        "260970000001",
        conversation_id="CONV-1",
        now=datetime(2026, 7, 20, 10, 0, tzinfo=UTC),
    )
    session.flow = flow
    session.stage = stage
    return session


@pytest.mark.asyncio
async def test_global_handover_rule_runs_before_model() -> None:
    model = StubModel({"intent": "faq", "confidence": 0.99, "entities": {}})
    interpreter = HybridInterpreter(model=model)

    intent = await interpreter.interpret("I need a human", _session())

    assert intent.type == IntentType.HANDOVER
    assert intent.role == MessageRole.GLOBAL_COMMAND
    assert model.calls == []


@pytest.mark.asyncio
async def test_correction_preserves_target_field_and_raw_text() -> None:
    interpreter = HybridInterpreter()

    intent = await interpreter.interpret("Change the quantity to 3", _session())

    assert intent.type == IntentType.CORRECT
    assert intent.entities.extras["field"] == "quantity"
    assert intent.entities.raw_text == "Change the quantity to 3"


@pytest.mark.asyncio
async def test_pending_numeric_item_selection() -> None:
    session = _session(flow=Flow.ORDER, stage=Stage.PRODUCT_CLARIFICATION)
    session.pending_question = PendingQuestion(
        prompt="Which product?",
        expected_intents=frozenset({IntentType.SELECT_ITEM}),
        metadata={"options": ["Boom 500g", "Boom 1kg"]},
    )

    intent = await HybridInterpreter().interpret("2", session)

    assert intent.type == IntentType.SELECT_ITEM
    assert intent.role == MessageRole.PENDING_ANSWER
    assert intent.entities.selection == 2


@pytest.mark.asyncio
async def test_pending_size_matches_saved_options() -> None:
    session = _session(flow=Flow.ORDER, stage=Stage.PRODUCT_CLARIFICATION)
    session.pending_question = PendingQuestion(
        prompt="Which size?",
        expected_intents=frozenset({IntentType.SELECT_ITEM}),
        metadata={"options": ["500g", "1kg"]},
    )

    intent = await HybridInterpreter().interpret("500 g", session)

    assert intent.type == IntentType.SELECT_ITEM
    assert intent.entities.selection == "500g"


@pytest.mark.asyncio
async def test_hours_question_interrupts_pending_product_selection() -> None:
    session = _session(flow=Flow.ORDER, stage=Stage.PRODUCT_CLARIFICATION)
    session.pending_question = PendingQuestion(
        prompt="Which size?",
        expected_intents=frozenset({IntentType.SELECT_ITEM}),
        metadata={"options": ["500g", "1kg"]},
    )

    intent = await HybridInterpreter().interpret("What time do you close?", session)

    assert intent.type == IntentType.BUSINESS_HOURS
    assert intent.role == MessageRole.SAFE_INTERRUPTION


@pytest.mark.asyncio
async def test_hours_rule_recognizes_ordinary_hours_today_wording() -> None:
    intent = await HybridInterpreter().interpret("What are your hours today?", _session())

    assert intent.type == IntentType.BUSINESS_HOURS
    assert intent.role == MessageRole.NEW_REQUEST


@pytest.mark.asyncio
async def test_pending_quantity_is_typed() -> None:
    session = _session(flow=Flow.ORDER, stage=Stage.QUANTITY)

    intent = await HybridInterpreter().interpret("3", session)

    assert intent.type == IntentType.PROVIDE_QUANTITY
    assert intent.entities.quantity == 3


@pytest.mark.asyncio
async def test_pending_delivery_method_is_typed() -> None:
    session = _session(flow=Flow.ORDER, stage=Stage.FULFILMENT_METHOD)

    intent = await HybridInterpreter().interpret("Please deliver it", session)

    assert intent.type == IntentType.PROVIDE_FULFILMENT_METHOD
    assert intent.entities.fulfilment_method == FulfilmentMethod.DELIVERY


@pytest.mark.asyncio
async def test_pending_customer_details_extract_name_and_phone() -> None:
    session = _session(flow=Flow.ORDER, stage=Stage.CUSTOMER_DETAILS)

    intent = await HybridInterpreter().interpret("James Chisulo 0970000000", session)

    assert intent.type == IntentType.PROVIDE_CUSTOMER_DETAILS
    assert intent.entities.customer_name == "James Chisulo"
    assert intent.entities.contact_number == "0970000000"


@pytest.mark.asyncio
async def test_pending_customer_name_starting_with_can_is_not_an_faq() -> None:
    session = _session(flow=Flow.ORDER, stage=Stage.CUSTOMER_DETAILS)

    intent = await HybridInterpreter().interpret(
        "Canonical Test +260000000015",
        session,
    )

    assert intent.type == IntentType.PROVIDE_CUSTOMER_DETAILS
    assert intent.entities.customer_name == "Canonical Test"
    assert intent.entities.contact_number == "260000000015"


@pytest.mark.asyncio
async def test_order_rule_captures_multiple_details_from_one_message() -> None:
    interpreter = HybridInterpreter()

    intent = await interpreter.interpret(
        "I want 2 small Boom packs delivered",
        _session(),
    )

    assert intent.type == IntentType.START_ORDER
    assert intent.entities.quantity == 2
    assert intent.entities.relative_size == RelativeSize.SMALL
    assert intent.entities.fulfilment_method == FulfilmentMethod.DELIVERY
    assert intent.entities.query == "2 small Boom packs delivered"


@pytest.mark.asyncio
async def test_order_rule_extracts_product_query_and_preserves_raw_text() -> None:
    intent = await HybridInterpreter().interpret("I want to order Anjoy", _session())

    assert intent.type == IntentType.START_ORDER
    assert intent.entities.query == "Anjoy"
    assert intent.entities.raw_text == "I want to order Anjoy"


@pytest.mark.asyncio
async def test_order_this_at_selected_product_stage_prompts_for_quantity() -> None:
    intent = await HybridInterpreter().interpret(
        "order this",
        _session(flow=Flow.ORDER, stage=Stage.PRODUCT_SELECTED),
    )

    assert intent.type == IntentType.PROVIDE_QUANTITY
    assert intent.role == MessageRole.PENDING_ANSWER
    assert intent.entities.quantity is None
    assert intent.reasoning_code == "pending_quantity_prompt_rule"


@pytest.mark.asyncio
async def test_order_this_with_pending_quantity_prompt_does_not_start_new_order() -> None:
    session = _session(flow=Flow.ORDER, stage=Stage.QUANTITY)
    session.set_pending_question(
        PendingQuestion(
            prompt="How many would you like?",
            expected_intents=frozenset({IntentType.PROVIDE_QUANTITY}),
        )
    )

    intent = await HybridInterpreter().interpret("order this", session)

    assert intent.type == IntentType.PROVIDE_QUANTITY
    assert intent.role == MessageRole.PENDING_ANSWER
    assert intent.entities.quantity is None
    assert intent.reasoning_code == "pending_quantity_prompt_rule"


@pytest.mark.asyncio
async def test_clear_rule_prevents_unnecessary_model_call() -> None:
    model = StubModel({"intent": "unknown", "confidence": 0.1, "entities": {}})
    interpreter = HybridInterpreter(model=model)

    intent = await interpreter.interpret("Are you open now?", _session())

    assert intent.type == IntentType.BUSINESS_HOURS
    assert model.calls == []


@pytest.mark.asyncio
async def test_catalogue_rule_extracts_product_query_and_preserves_raw_text() -> None:
    intent = await HybridInterpreter().interpret("Do you have Anjoy?", _session())

    assert intent.type == IntentType.CATALOGUE_SEARCH
    assert intent.entities.query == "Anjoy"
    assert intent.entities.raw_text == "Do you have Anjoy?"


@pytest.mark.asyncio
async def test_model_fallback_is_used_for_unmatched_language() -> None:
    model = StubModel(
        {
            "intent": "catalogue_search",
            "role": "new_request",
            "confidence": 0.88,
            "entities": {"query": "something for washing clothes"},
        }
    )
    interpreter = HybridInterpreter(model=model)

    intent = await interpreter.interpret(
        "Something for washing clothes",
        _session(),
        capabilities=frozenset({Capability.PRODUCT_CATALOGUE}),
    )

    assert intent.type == IntentType.CATALOGUE_SEARCH
    assert len(model.calls) == 1


@pytest.mark.asyncio
async def test_invalid_model_output_becomes_clarification() -> None:
    model = StubModel(
        {
            "intent": "catalogue_search",
            "confidence": 0.99,
            "entities": {"selling_price": 24},
        }
    )
    interpreter = HybridInterpreter(model=model)

    intent = await interpreter.interpret("Maybe that detergent", _session())

    assert intent.type == IntentType.CLARIFY
    assert intent.reasoning_code == "model_output_rejected"


def test_model_context_is_bounded_and_contains_pending_state() -> None:
    session = _session(flow=Flow.ORDER, stage=Stage.PRODUCT_CLARIFICATION)
    session.pending_question = PendingQuestion(
        prompt="Which size?",
        expected_intents=frozenset({IntentType.SELECT_ITEM}),
        metadata={"options": ["500g", "1kg"]},
    )
    for index in range(8):
        session.recent_history.append(ConversationTurn(role="customer", text=f"Message {index}"))

    context = build_model_context(
        session,
        frozenset({Capability.PRODUCT_CATALOGUE, Capability.PRODUCT_ORDER}),
    )

    assert context["flow"] == "order"
    assert context["stage"] == "product_clarification"
    assert context["pending_question"] is not None
    assert len(context["recent_history"]) == 6
    assert context["enabled_capabilities"] == ["product.catalogue", "product.order"]
    assert context["allowed_actions"] == [
        "cancel",
        "catalogue_search",
        "clarify",
        "close_session",
        "confirm",
        "continue",
        "correct",
        "provide_fulfilment_method",
        "provide_quantity",
        "resume_bot",
        "select_item",
        "start_order",
    ]


@pytest.mark.asyncio
async def test_model_fallback_receives_capability_scope() -> None:
    model = StubModel(
        {
            "intent": "catalogue_search",
            "role": "new_request",
            "confidence": 0.88,
            "entities": {"query": "something for washing clothes"},
        }
    )
    interpreter = HybridInterpreter(model=model)

    await interpreter.interpret(
        "Something for washing clothes",
        _session(),
        capabilities=frozenset({Capability.PRODUCT_CATALOGUE}),
    )

    assert model.calls[0][1]["enabled_capabilities"] == ["product.catalogue"]


def test_allowed_actions_exclude_harvest_booking_and_include_serah_booking() -> None:
    harvest_actions = allowed_actions_for_capabilities(
        frozenset({Capability.PRODUCT_CATALOGUE, Capability.PRODUCT_ORDER})
    )
    serah_actions = allowed_actions_for_capabilities(
        frozenset(
            {
                Capability.PRODUCT_CATALOGUE,
                Capability.PRODUCT_ORDER,
                Capability.SERVICE_CATALOGUE,
                Capability.APPOINTMENT_CREATE,
            }
        )
    )

    assert IntentType.START_BOOKING not in harvest_actions
    assert IntentType.START_BOOKING in serah_actions


@pytest.mark.asyncio
async def test_model_proposed_unavailable_action_is_rejected() -> None:
    model = StubModel(
        {
            "intent": "start_booking",
            "role": "new_request",
            "confidence": 0.95,
            "entities": {"query": "book a haircut"},
        }
    )
    interpreter = HybridInterpreter(model=model)

    intent = await interpreter.interpret(
        "Something relaxing tomorrow",
        _session(),
        capabilities=frozenset({Capability.PRODUCT_CATALOGUE, Capability.PRODUCT_ORDER}),
    )

    assert intent.type == IntentType.CLARIFY
    assert intent.reasoning_code == "model_output_rejected"
    assert "start_booking" not in model.calls[0][1]["allowed_actions"]


@pytest.mark.asyncio
async def test_pending_product_suggestion_accepts_yes_only_when_enabled() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.flow = Flow.CATALOGUE
    session.stage = Stage.ITEM_SELECTION
    session.set_pending_question(
        PendingQuestion(
            prompt="Is this the product you mean?",
            expected_intents=frozenset({IntentType.SELECT_ITEM}),
            metadata={
                "options": ("Boom Washing Powder 500g",),
                "allow_confirmation": True,
            },
        )
    )

    intent = await HybridInterpreter().interpret("yes", session)

    assert intent.type == IntentType.SELECT_ITEM
    assert intent.role == MessageRole.PENDING_ANSWER
    assert intent.entities.selection == "yes"


@pytest.mark.asyncio
async def test_pending_multi_option_selection_does_not_accept_yes_without_flag() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.flow = Flow.CATALOGUE
    session.stage = Stage.PRODUCT_CLARIFICATION
    session.set_pending_question(
        PendingQuestion(
            prompt="Which product would you like?",
            expected_intents=frozenset({IntentType.SELECT_ITEM}),
            metadata={"options": ("Boom 500g", "Boom 1kg")},
        )
    )

    intent = await HybridInterpreter().interpret("yes", session)

    assert intent.type == IntentType.CLARIFY


@pytest.mark.asyncio
async def test_product_size_is_not_mistaken_for_order_quantity() -> None:
    intent = await HybridInterpreter().interpret(
        "order Boom 500g",
        _session(),
    )

    assert intent.type == IntentType.START_ORDER
    assert intent.entities.quantity is None


@pytest.mark.asyncio
async def test_word_quantity_is_understood_when_quantity_is_pending() -> None:
    session = _session(flow=Flow.ORDER, stage=Stage.QUANTITY)

    intent = await HybridInterpreter().interpret("two", session)

    assert intent.type == IntentType.PROVIDE_QUANTITY
    assert intent.entities.quantity == 2
