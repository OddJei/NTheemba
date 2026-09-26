"""Tests for typed interpretation models."""

from __future__ import annotations

import pytest
from ntheemba.domain.enums import IntentType, MessageRole
from ntheemba.domain.intents import EntitySet, Intent, PendingQuestion


def test_intent_accepts_valid_confidence() -> None:
    intent = Intent(
        type=IntentType.START_ORDER,
        role=MessageRole.NEW_REQUEST,
        confidence=0.92,
        entities=EntitySet(query="small Boom", quantity=2),
    )

    assert intent.entities.quantity == 2


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_intent_rejects_invalid_confidence(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        Intent(
            type=IntentType.UNKNOWN,
            role=MessageRole.UNKNOWN,
            confidence=confidence,
        )


def test_pending_question_requires_expected_intent() -> None:
    with pytest.raises(ValueError, match="at least one"):
        PendingQuestion(prompt="Which size?", expected_intents=frozenset())
