"""Tests for the central transition policy."""

from __future__ import annotations

import pytest
from ntheemba.domain.enums import ConversationMode, Flow, IntentType, SessionStatus, Stage
from ntheemba.domain.transitions import (
    InvalidTransitionError,
    TransitionContext,
    TransitionPolicy,
    TransitionTarget,
)


def test_order_quantity_accepts_quantity_action() -> None:
    policy = TransitionPolicy()
    context = TransitionContext(
        flow=Flow.ORDER,
        stage=Stage.QUANTITY,
        mode=ConversationMode.BOT,
        status=SessionStatus.ACTIVE,
    )

    policy.require_action(context, IntentType.PROVIDE_QUANTITY)


def test_order_quantity_rejects_booking_time_action() -> None:
    policy = TransitionPolicy()
    context = TransitionContext(
        flow=Flow.ORDER,
        stage=Stage.QUANTITY,
        mode=ConversationMode.BOT,
        status=SessionStatus.ACTIVE,
    )

    with pytest.raises(InvalidTransitionError):
        policy.require_action(context, IntentType.SELECT_TIME)


def test_active_order_allows_safe_business_hours_interruption() -> None:
    policy = TransitionPolicy()
    context = TransitionContext(
        flow=Flow.ORDER,
        stage=Stage.PRODUCT_CLARIFICATION,
        mode=ConversationMode.BOT,
        status=SessionStatus.ACTIVE,
    )

    policy.require_action(context, IntentType.BUSINESS_HOURS)
    policy.require_target(
        context,
        TransitionTarget(flow=Flow.INFORMATION, stage=Stage.INFORMATION_LOOKUP),
    )


def test_handover_target_must_pause_in_human_mode() -> None:
    policy = TransitionPolicy()
    context = TransitionContext(
        flow=Flow.ORDER,
        stage=Stage.QUANTITY,
        mode=ConversationMode.BOT,
        status=SessionStatus.ACTIVE,
    )

    with pytest.raises(InvalidTransitionError, match="pause"):
        policy.require_target(
            context,
            TransitionTarget(
                flow=Flow.HANDOVER,
                stage=Stage.WAITING_FOR_HUMAN,
                mode=ConversationMode.BOT,
                status=SessionStatus.ACTIVE,
            ),
        )
