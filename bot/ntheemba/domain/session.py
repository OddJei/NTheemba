"""Conversation session aggregate and protected state-changing behaviour."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ntheemba.domain.booking_draft import BookingDraft
from ntheemba.domain.enums import (
    ConversationMode,
    Flow,
    HandoverStatus,
    IntentType,
    SessionStatus,
    Stage,
)
from ntheemba.domain.intents import PendingQuestion
from ntheemba.domain.order_draft import OrderDraft
from ntheemba.domain.product_resolution import ProductResolution
from ntheemba.domain.transitions import TransitionContext, TransitionPolicy, TransitionTarget


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime values must be timezone-aware")
    return value


class SessionStateError(ValueError):
    """Raised when a session invariant would be broken."""


class ClarificationLimitReached(SessionStateError):
    """Raised when repeated clarification should trigger handover."""


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    role: str
    text: str
    message_id: str = ""
    at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if self.role not in {"customer", "assistant", "human", "system"}:
            raise ValueError("unsupported conversation-turn role")
        if not self.text.strip():
            raise ValueError("conversation-turn text must not be empty")
        _ensure_aware(self.at)


@dataclass(frozen=True, slots=True)
class SuspendedState:
    flow: Flow
    stage: Stage
    pending_question: PendingQuestion | None = None

    def __post_init__(self) -> None:
        if self.flow in {Flow.IDLE, Flow.INFORMATION, Flow.FAQ, Flow.HANDOVER}:
            raise ValueError("only customer workflows can be suspended")


@dataclass(slots=True)
class Session:
    conversation_id: str
    business_id: str
    customer_id: str
    flow: Flow = Flow.IDLE
    stage: Stage = Stage.START
    mode: ConversationMode = ConversationMode.BOT
    status: SessionStatus = SessionStatus.ACTIVE
    handover_status: HandoverStatus = HandoverStatus.NONE
    order_draft: OrderDraft | None = None
    booking_draft: BookingDraft | None = None
    product_resolution: ProductResolution | None = None
    pending_question: PendingQuestion | None = None
    suspended_state: SuspendedState | None = None
    recent_history: list[ConversationTurn] = field(default_factory=list)
    conversation_summary: str = ""
    clarification_count: int = 0
    revision: int = 0
    started_at: datetime = field(default_factory=_utc_now)
    last_activity_at: datetime = field(default_factory=_utc_now)
    expires_at: datetime = field(default_factory=lambda: _utc_now() + timedelta(hours=24))

    def __post_init__(self) -> None:
        if not self.conversation_id.strip():
            raise ValueError("conversation_id must not be empty")
        if not self.business_id.strip():
            raise ValueError("business_id must not be empty")
        if not self.customer_id.strip():
            raise ValueError("customer_id must not be empty")
        _ensure_aware(self.started_at)
        _ensure_aware(self.last_activity_at)
        _ensure_aware(self.expires_at)
        if self.expires_at <= self.started_at:
            raise ValueError("expires_at must be later than started_at")
        if self.revision < 0:
            raise ValueError("revision must not be negative")
        if self.clarification_count < 0:
            raise ValueError("clarification_count must not be negative")

    @classmethod
    def create(
        cls,
        business_id: str,
        customer_id: str,
        *,
        conversation_id: str | None = None,
        now: datetime | None = None,
        ttl: timedelta = timedelta(hours=24),
    ) -> Session:
        moment = _ensure_aware(now or _utc_now())
        if ttl <= timedelta(0):
            raise ValueError("ttl must be greater than zero")
        return cls(
            conversation_id=conversation_id or f"CONV-{uuid4()}",
            business_id=business_id,
            customer_id=customer_id,
            started_at=moment,
            last_activity_at=moment,
            expires_at=moment + ttl,
        )

    def transition_context(self) -> TransitionContext:
        return TransitionContext(self.flow, self.stage, self.mode, self.status)

    def authorize(self, policy: TransitionPolicy, action: IntentType) -> None:
        policy.require_action(self.transition_context(), action)

    def transition_to(
        self,
        policy: TransitionPolicy,
        flow: Flow,
        stage: Stage,
        *,
        mode: ConversationMode | None = None,
        status: SessionStatus | None = None,
    ) -> None:
        target = TransitionTarget(
            flow=flow,
            stage=stage,
            mode=mode or self.mode,
            status=status or self.status,
        )
        policy.require_target(self.transition_context(), target)
        self.flow = target.flow
        self.stage = target.stage
        self.mode = target.mode
        self.status = target.status

    def suspend_for_side_question(
        self,
        policy: TransitionPolicy,
        *,
        flow: Flow,
        stage: Stage,
        question: PendingQuestion | None = None,
    ) -> None:
        if self.suspended_state is not None:
            raise SessionStateError("nested workflow suspension is not supported")
        if self.flow not in {Flow.CATALOGUE, Flow.ORDER, Flow.BOOKING}:
            raise SessionStateError("the current flow cannot be suspended")
        self.suspended_state = SuspendedState(self.flow, self.stage, self.pending_question)
        self.transition_to(policy, flow, stage)
        self.pending_question = question

    def resume_suspended(self, policy: TransitionPolicy) -> None:
        if self.suspended_state is None:
            raise SessionStateError("there is no suspended workflow")
        suspended = self.suspended_state
        target = TransitionTarget(
            suspended.flow,
            suspended.stage,
            ConversationMode.BOT,
            SessionStatus.ACTIVE,
        )
        policy.require_resume(self.transition_context(), target)
        self.flow = target.flow
        self.stage = target.stage
        self.mode = target.mode
        self.status = target.status
        self.pending_question = suspended.pending_question
        self.suspended_state = None

    def set_pending_question(self, question: PendingQuestion) -> None:
        self.pending_question = question

    def clear_pending_question(self) -> None:
        self.pending_question = None

    def request_clarification(
        self,
        question: PendingQuestion,
        *,
        maximum_attempts: int = 3,
    ) -> None:
        if maximum_attempts <= 0:
            raise ValueError("maximum_attempts must be greater than zero")
        self.clarification_count += 1
        self.pending_question = question
        if self.clarification_count > maximum_attempts:
            raise ClarificationLimitReached("maximum clarification attempts have been exceeded")

    def clear_clarification(self) -> None:
        self.clarification_count = 0
        self.pending_question = None

    def request_handover(
        self,
        policy: TransitionPolicy,
        *,
        preserve_workflow: bool = True,
    ) -> None:
        self.authorize(policy, IntentType.HANDOVER)
        if (
            preserve_workflow
            and self.flow in {Flow.CATALOGUE, Flow.ORDER, Flow.BOOKING}
            and self.suspended_state is None
        ):
            self.suspended_state = SuspendedState(self.flow, self.stage, self.pending_question)
        self.transition_to(
            policy,
            Flow.HANDOVER,
            Stage.WAITING_FOR_HUMAN,
            mode=ConversationMode.HUMAN,
            status=SessionStatus.PAUSED,
        )
        self.handover_status = HandoverStatus.WAITING
        self.pending_question = None

    def mark_human_active(self, policy: TransitionPolicy) -> None:
        self.transition_to(
            policy,
            Flow.HANDOVER,
            Stage.HUMAN_ACTIVE,
            mode=ConversationMode.HUMAN,
            status=SessionStatus.PAUSED,
        )
        self.handover_status = HandoverStatus.ACTIVE

    def resume_bot(self, policy: TransitionPolicy) -> None:
        self.authorize(policy, IntentType.RESUME_BOT)
        self.handover_status = HandoverStatus.RESOLVED
        if self.suspended_state is not None:
            self.resume_suspended(policy)
            return
        self.flow = Flow.IDLE
        self.stage = Stage.START
        self.mode = ConversationMode.BOT
        self.status = SessionStatus.ACTIVE

    def cancel_active_flow(self, policy: TransitionPolicy) -> None:
        self.authorize(policy, IntentType.CANCEL)
        self.transition_to(policy, Flow.IDLE, Stage.CANCELLED)
        self.order_draft = None
        self.booking_draft = None
        self.product_resolution = None
        self.pending_question = None
        self.suspended_state = None
        self.clarification_count = 0

    def close(self) -> None:
        self.flow = Flow.IDLE
        self.stage = Stage.CLOSED
        self.mode = ConversationMode.HUMAN
        self.status = SessionStatus.CLOSED
        self.handover_status = HandoverStatus.RESOLVED
        self.pending_question = None
        self.suspended_state = None

    def expire(self, *, now: datetime | None = None) -> None:
        moment = _ensure_aware(now or _utc_now())
        if moment < self.expires_at:
            raise SessionStateError("session has not reached its expiry time")
        self.flow = Flow.IDLE
        self.stage = Stage.CLOSED
        self.status = SessionStatus.EXPIRED
        self.pending_question = None
        self.suspended_state = None

    def touch(self, *, now: datetime | None = None, ttl: timedelta | None = None) -> None:
        moment = _ensure_aware(now or _utc_now())
        if moment < self.last_activity_at:
            raise ValueError("last_activity_at cannot move backwards")
        self.last_activity_at = moment
        if ttl is not None:
            if ttl <= timedelta(0):
                raise ValueError("ttl must be greater than zero")
            self.expires_at = moment + ttl

    def append_history(self, turn: ConversationTurn, *, maximum_entries: int = 20) -> None:
        if maximum_entries <= 0:
            raise ValueError("maximum_entries must be greater than zero")
        self.recent_history.append(turn)
        overflow = len(self.recent_history) - maximum_entries
        if overflow > 0:
            del self.recent_history[:overflow]
