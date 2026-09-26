"""Tests for untrusted interpretation validation."""

from __future__ import annotations

from datetime import date, time

import pytest
from ntheemba.domain.enums import (
    FulfilmentMethod,
    IntentType,
    ItemType,
    MessageRole,
    RelativeSize,
)
from ntheemba.services.validation import (
    InterpretationValidationError,
    ModelOutputValidator,
)


def test_validator_converts_model_payload_to_typed_intent() -> None:
    validator = ModelOutputValidator(minimum_confidence=0.6)

    intent = validator.validate(
        {
            "intent": "start_order",
            "role": "new_request",
            "confidence": 0.94,
            "entities": {
                "query": "two small Boom packs delivered",
                "quantity": 2,
                "fulfilment_method": "delivery",
                "item_type": "product",
                "relative_size": "small",
                "preferred_date": "2026-07-25",
                "start_time": "09:30",
            },
        },
        raw_text="I want two small Boom packs delivered",
    )

    assert intent.type == IntentType.START_ORDER
    assert intent.role == MessageRole.NEW_REQUEST
    assert intent.entities.quantity == 2
    assert intent.entities.fulfilment_method == FulfilmentMethod.DELIVERY
    assert intent.entities.item_type == ItemType.PRODUCT
    assert intent.entities.relative_size == RelativeSize.SMALL
    assert intent.entities.preferred_date == date(2026, 7, 25)
    assert intent.entities.start_time == time(9, 30)


def test_low_confidence_model_output_becomes_clarification() -> None:
    validator = ModelOutputValidator(minimum_confidence=0.7)

    intent = validator.validate(
        {
            "intent": "start_order",
            "confidence": 0.45,
            "entities": {"quantity": 2},
        },
        raw_text="that one",
    )

    assert intent.type == IntentType.CLARIFY
    assert intent.role == MessageRole.UNKNOWN
    assert intent.reasoning_code == "model_confidence_below_threshold"
    assert intent.entities.raw_text == "that one"


@pytest.mark.parametrize(
    "entities",
    [
        {"price": 24},
        {"stock": 10},
        {"extras": {"available_quantity": 10}},
        {"business_product_id": "BP-1"},
    ],
)
def test_model_cannot_assert_external_business_facts(entities: dict[str, object]) -> None:
    validator = ModelOutputValidator()

    with pytest.raises(InterpretationValidationError, match="external business fact"):
        validator.validate(
            {
                "intent": "catalogue_search",
                "confidence": 0.9,
                "entities": entities,
            },
            raw_text="Do you have Boom?",
        )


def test_validator_rejects_unknown_entity_fields() -> None:
    validator = ModelOutputValidator()

    with pytest.raises(InterpretationValidationError, match="unsupported entity field"):
        validator.validate(
            {
                "intent": "faq",
                "confidence": 0.9,
                "entities": {"secret_instruction": "ignore rules"},
            },
            raw_text="help",
        )


def test_validator_rejects_unsupported_intent() -> None:
    validator = ModelOutputValidator()

    with pytest.raises(InterpretationValidationError, match="unsupported intent"):
        validator.validate(
            {
                "intent": "delete_inventory",
                "confidence": 0.99,
                "entities": {},
            },
            raw_text="delete everything",
        )
