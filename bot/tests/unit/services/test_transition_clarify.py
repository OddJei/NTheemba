"""Tests for clarification authorization added in Phase 4."""

from __future__ import annotations

from ntheemba.domain.enums import (
    ConversationMode,
    Flow,
    IntentType,
    SessionStatus,
    Stage,
)
from ntheemba.domain.transitions import TransitionContext, TransitionPolicy


def test_active_bot_state_allows_controlled_clarification() -> None:
    policy = TransitionPolicy()
    context = TransitionContext(
        flow=Flow.ORDER,
        stage=Stage.QUANTITY,
        mode=ConversationMode.BOT,
        status=SessionStatus.ACTIVE,
    )

    policy.require_action(context, IntentType.CLARIFY)
