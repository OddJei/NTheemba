"""Tests for the conversation session aggregate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from ntheemba.domain.enums import (
    ConversationMode,
    Flow,
    HandoverStatus,
    IntentType,
    SessionStatus,
    Stage,
)
from ntheemba.domain.intents import PendingQuestion
from ntheemba.domain.session import ClarificationLimitReached, ConversationTurn, Session
from ntheemba.domain.transitions import TransitionPolicy


def _session() -> Session:
    return Session.create(
        "BUS-001",
        "260970000000",
        conversation_id="CONV-001",
        now=datetime(2026, 7, 20, 10, 0, tzinfo=UTC),
    )


def test_session_suspends_and_resumes_product_clarification() -> None:
    session = _session()
    policy = TransitionPolicy()
    session.transition_to(policy, Flow.ORDER, Stage.CATALOGUE_SEARCH)
    session.transition_to(policy, Flow.ORDER, Stage.PRODUCT_CLARIFICATION)
    product_question = PendingQuestion(
        prompt="Which size would you like?",
        expected_intents=frozenset({IntentType.SELECT_ITEM}),
    )
    session.set_pending_question(product_question)

    session.suspend_for_side_question(
        policy,
        flow=Flow.INFORMATION,
        stage=Stage.INFORMATION_LOOKUP,
    )

    assert session.flow.value == Flow.INFORMATION.value
    assert session.suspended_state is not None

    session.resume_suspended(policy)

    assert session.flow == Flow.ORDER
    assert session.stage == Stage.PRODUCT_CLARIFICATION
    assert session.pending_question == product_question


def test_session_handover_preserves_and_restores_workflow() -> None:
    session = _session()
    policy = TransitionPolicy()
    session.transition_to(policy, Flow.ORDER, Stage.CATALOGUE_SEARCH)
    session.transition_to(policy, Flow.ORDER, Stage.PRODUCT_SELECTED)
    session.transition_to(policy, Flow.ORDER, Stage.QUANTITY)

    session.request_handover(policy)

    assert session.mode.value == ConversationMode.HUMAN.value
    assert session.status.value == SessionStatus.PAUSED.value
    assert session.handover_status == HandoverStatus.WAITING

    session.resume_bot(policy)

    assert session.mode == ConversationMode.BOT
    assert session.status == SessionStatus.ACTIVE
    assert session.flow == Flow.ORDER
    assert session.stage == Stage.QUANTITY


def test_clarification_limit_signals_handover_need() -> None:
    session = _session()
    question = PendingQuestion(
        prompt="Please choose 1 or 2.",
        expected_intents=frozenset({IntentType.SELECT_ITEM}),
    )

    for _ in range(3):
        session.request_clarification(question, maximum_attempts=3)

    with pytest.raises(ClarificationLimitReached):
        session.request_clarification(question, maximum_attempts=3)


def test_recent_history_is_bounded() -> None:
    session = _session()

    for index in range(5):
        session.append_history(
            ConversationTurn(role="customer", text=f"Message {index}"),
            maximum_entries=3,
        )

    assert [turn.text for turn in session.recent_history] == [
        "Message 2",
        "Message 3",
        "Message 4",
    ]


def test_session_expires_only_after_ttl() -> None:
    session = _session()

    with pytest.raises(ValueError, match="not reached"):
        session.expire(now=session.expires_at - timedelta(seconds=1))

    session.expire(now=session.expires_at)

    assert session.status == SessionStatus.EXPIRED
    assert session.stage == Stage.CLOSED
