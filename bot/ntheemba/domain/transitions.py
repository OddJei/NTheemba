"""Central workflow action and state-transition policy."""

from __future__ import annotations

from dataclasses import dataclass

from ntheemba.domain.enums import ConversationMode, Flow, IntentType, SessionStatus, Stage


class InvalidTransitionError(ValueError):
    """Raised when an action or target state is not permitted."""


@dataclass(frozen=True, slots=True)
class TransitionContext:
    flow: Flow
    stage: Stage
    mode: ConversationMode
    status: SessionStatus


@dataclass(frozen=True, slots=True)
class TransitionTarget:
    flow: Flow
    stage: Stage
    mode: ConversationMode = ConversationMode.BOT
    status: SessionStatus = SessionStatus.ACTIVE


StateKey = tuple[Flow, Stage]
StateTarget = tuple[Flow, Stage]

_GLOBAL_ACTIONS = frozenset({IntentType.HANDOVER, IntentType.CANCEL, IntentType.CORRECT})
_SAFE_INTERRUPTS = frozenset(
    {
        IntentType.BUSINESS_INFO,
        IntentType.BUSINESS_HOURS,
        IntentType.FAQ,
        IntentType.LOYALTY_STATUS,
    }
)

_ALLOWED_ACTIONS: dict[StateKey, frozenset[IntentType]] = {
    (Flow.IDLE, Stage.START): frozenset(
        {
            IntentType.BUSINESS_INFO,
            IntentType.BUSINESS_HOURS,
            IntentType.FAQ,
            IntentType.LOYALTY_STATUS,
            IntentType.CATALOGUE_SEARCH,
            IntentType.START_ORDER,
            IntentType.START_BOOKING,
            IntentType.HANDOVER,
        }
    ),
    (Flow.IDLE, Stage.CANCELLED): frozenset(
        {
            IntentType.CONTINUE,
            IntentType.BUSINESS_INFO,
            IntentType.BUSINESS_HOURS,
            IntentType.FAQ,
            IntentType.LOYALTY_STATUS,
            IntentType.CATALOGUE_SEARCH,
            IntentType.START_ORDER,
            IntentType.START_BOOKING,
            IntentType.HANDOVER,
        }
    ),
    (Flow.IDLE, Stage.RESOLVED): frozenset(
        {
            IntentType.CONTINUE,
            IntentType.BUSINESS_INFO,
            IntentType.BUSINESS_HOURS,
            IntentType.FAQ,
            IntentType.LOYALTY_STATUS,
            IntentType.CATALOGUE_SEARCH,
            IntentType.START_ORDER,
            IntentType.START_BOOKING,
            IntentType.HANDOVER,
        }
    ),
    (Flow.INFORMATION, Stage.INFORMATION_LOOKUP): frozenset(
        {
            IntentType.BUSINESS_INFO,
            IntentType.BUSINESS_HOURS,
            IntentType.CONTINUE,
        }
    ),
    (Flow.FAQ, Stage.FAQ_SEARCH): frozenset({IntentType.FAQ, IntentType.CONTINUE}),
    (Flow.CATALOGUE, Stage.CATALOGUE_SEARCH): frozenset(
        {
            IntentType.CATALOGUE_SEARCH,
            IntentType.SELECT_ITEM,
            IntentType.START_ORDER,
            IntentType.START_BOOKING,
        }
    ),
    (Flow.CATALOGUE, Stage.ITEM_SELECTION): frozenset(
        {
            IntentType.SELECT_ITEM,
            IntentType.CATALOGUE_SEARCH,
            IntentType.START_ORDER,
            IntentType.START_BOOKING,
        }
    ),
    (Flow.CATALOGUE, Stage.PRODUCT_CLARIFICATION): frozenset({IntentType.SELECT_ITEM}),
    (Flow.CATALOGUE, Stage.PRODUCT_SELECTED): frozenset(
        {
            IntentType.START_ORDER,
            IntentType.START_BOOKING,
            IntentType.CATALOGUE_SEARCH,
        }
    ),
    (Flow.ORDER, Stage.CATALOGUE_SEARCH): frozenset(
        {
            IntentType.CATALOGUE_SEARCH,
            IntentType.SELECT_ITEM,
        }
    ),
    (Flow.ORDER, Stage.ITEM_SELECTION): frozenset({IntentType.SELECT_ITEM}),
    (Flow.ORDER, Stage.PRODUCT_CLARIFICATION): frozenset({IntentType.SELECT_ITEM}),
    (Flow.ORDER, Stage.PRODUCT_SELECTED): frozenset({IntentType.PROVIDE_QUANTITY}),
    (Flow.ORDER, Stage.QUANTITY): frozenset({IntentType.PROVIDE_QUANTITY}),
    (Flow.ORDER, Stage.FULFILMENT_METHOD): frozenset({IntentType.PROVIDE_FULFILMENT_METHOD}),
    (Flow.ORDER, Stage.DELIVERY_DETAILS): frozenset({IntentType.PROVIDE_DELIVERY_DETAILS}),
    (Flow.ORDER, Stage.CUSTOMER_DETAILS): frozenset({IntentType.PROVIDE_CUSTOMER_DETAILS}),
    (Flow.ORDER, Stage.ORDER_REVIEW): frozenset({IntentType.CONFIRM}),
    (Flow.ORDER, Stage.CUSTOMER_CONFIRMATION): frozenset({IntentType.CONFIRM}),
    (Flow.ORDER, Stage.SUBMITTING): frozenset(),
    (Flow.ORDER, Stage.SUBMITTED): frozenset({IntentType.CONTINUE, IntentType.CONFIRM}),
    (Flow.BOOKING, Stage.SERVICE_SELECTION): frozenset(
        {
            IntentType.CATALOGUE_SEARCH,
            IntentType.SELECT_ITEM,
        }
    ),
    (Flow.BOOKING, Stage.PREFERRED_DATE): frozenset({IntentType.PROVIDE_DATE}),
    (Flow.BOOKING, Stage.TIME_SELECTION): frozenset({IntentType.SELECT_TIME}),
    (Flow.BOOKING, Stage.STAFF_SELECTION): frozenset({IntentType.SELECT_STAFF}),
    (Flow.BOOKING, Stage.CUSTOMER_DETAILS): frozenset({IntentType.PROVIDE_CUSTOMER_DETAILS}),
    (Flow.BOOKING, Stage.BOOKING_REVIEW): frozenset({IntentType.CONFIRM}),
    (Flow.BOOKING, Stage.CUSTOMER_CONFIRMATION): frozenset({IntentType.CONFIRM}),
    (Flow.BOOKING, Stage.SUBMITTING): frozenset(),
    (Flow.BOOKING, Stage.SUBMITTED): frozenset({IntentType.CONTINUE, IntentType.CONFIRM}),
    (Flow.HANDOVER, Stage.WAITING_FOR_HUMAN): frozenset(
        {
            IntentType.RESUME_BOT,
            IntentType.CLOSE_SESSION,
        }
    ),
    (Flow.HANDOVER, Stage.HUMAN_ACTIVE): frozenset(
        {
            IntentType.RESUME_BOT,
            IntentType.CLOSE_SESSION,
        }
    ),
}

_ALLOWED_TARGETS: dict[StateKey, frozenset[StateTarget]] = {
    (Flow.IDLE, Stage.START): frozenset(
        {
            (Flow.INFORMATION, Stage.INFORMATION_LOOKUP),
            (Flow.FAQ, Stage.FAQ_SEARCH),
            (Flow.CATALOGUE, Stage.CATALOGUE_SEARCH),
            (Flow.ORDER, Stage.CATALOGUE_SEARCH),
            (Flow.BOOKING, Stage.SERVICE_SELECTION),
        }
    ),
    (Flow.IDLE, Stage.CANCELLED): frozenset({(Flow.IDLE, Stage.START)}),
    (Flow.IDLE, Stage.RESOLVED): frozenset({(Flow.IDLE, Stage.START)}),
    (Flow.INFORMATION, Stage.INFORMATION_LOOKUP): frozenset({(Flow.IDLE, Stage.START)}),
    (Flow.FAQ, Stage.FAQ_SEARCH): frozenset({(Flow.IDLE, Stage.START)}),
    (Flow.CATALOGUE, Stage.CATALOGUE_SEARCH): frozenset(
        {
            (Flow.CATALOGUE, Stage.ITEM_SELECTION),
            (Flow.CATALOGUE, Stage.PRODUCT_CLARIFICATION),
            (Flow.CATALOGUE, Stage.PRODUCT_SELECTED),
            (Flow.IDLE, Stage.START),
        }
    ),
    (Flow.CATALOGUE, Stage.ITEM_SELECTION): frozenset(
        {
            (Flow.CATALOGUE, Stage.PRODUCT_CLARIFICATION),
            (Flow.CATALOGUE, Stage.PRODUCT_SELECTED),
            (Flow.CATALOGUE, Stage.CATALOGUE_SEARCH),
            (Flow.ORDER, Stage.PRODUCT_SELECTED),
            (Flow.BOOKING, Stage.PREFERRED_DATE),
        }
    ),
    (Flow.CATALOGUE, Stage.PRODUCT_CLARIFICATION): frozenset(
        {
            (Flow.CATALOGUE, Stage.PRODUCT_SELECTED),
            (Flow.CATALOGUE, Stage.CATALOGUE_SEARCH),
        }
    ),
    (Flow.CATALOGUE, Stage.PRODUCT_SELECTED): frozenset(
        {
            (Flow.ORDER, Stage.QUANTITY),
            (Flow.BOOKING, Stage.PREFERRED_DATE),
            (Flow.CATALOGUE, Stage.CATALOGUE_SEARCH),
        }
    ),
    (Flow.ORDER, Stage.CATALOGUE_SEARCH): frozenset(
        {
            (Flow.ORDER, Stage.ITEM_SELECTION),
            (Flow.ORDER, Stage.PRODUCT_CLARIFICATION),
            (Flow.ORDER, Stage.PRODUCT_SELECTED),
            (Flow.ORDER, Stage.QUANTITY),
            (Flow.ORDER, Stage.FULFILMENT_METHOD),
            (Flow.ORDER, Stage.DELIVERY_DETAILS),
            (Flow.ORDER, Stage.CUSTOMER_DETAILS),
        }
    ),
    (Flow.ORDER, Stage.ITEM_SELECTION): frozenset(
        {
            (Flow.ORDER, Stage.PRODUCT_CLARIFICATION),
            (Flow.ORDER, Stage.PRODUCT_SELECTED),
            (Flow.ORDER, Stage.CATALOGUE_SEARCH),
        }
    ),
    (Flow.ORDER, Stage.PRODUCT_CLARIFICATION): frozenset(
        {
            (Flow.ORDER, Stage.PRODUCT_SELECTED),
            (Flow.ORDER, Stage.CATALOGUE_SEARCH),
        }
    ),
    (Flow.ORDER, Stage.PRODUCT_SELECTED): frozenset(
        {
            (Flow.ORDER, Stage.CATALOGUE_SEARCH),
            (Flow.ORDER, Stage.QUANTITY),
            (Flow.ORDER, Stage.FULFILMENT_METHOD),
            (Flow.ORDER, Stage.DELIVERY_DETAILS),
            (Flow.ORDER, Stage.CUSTOMER_DETAILS),
        }
    ),
    (Flow.ORDER, Stage.QUANTITY): frozenset(
        {
            (Flow.ORDER, Stage.CATALOGUE_SEARCH),
            (Flow.ORDER, Stage.FULFILMENT_METHOD),
            (Flow.ORDER, Stage.DELIVERY_DETAILS),
            (Flow.ORDER, Stage.CUSTOMER_DETAILS),
            (Flow.ORDER, Stage.ORDER_REVIEW),
        }
    ),
    (Flow.ORDER, Stage.FULFILMENT_METHOD): frozenset(
        {
            (Flow.ORDER, Stage.CATALOGUE_SEARCH),
            (Flow.ORDER, Stage.QUANTITY),
            (Flow.ORDER, Stage.DELIVERY_DETAILS),
            (Flow.ORDER, Stage.CUSTOMER_DETAILS),
            (Flow.ORDER, Stage.ORDER_REVIEW),
        }
    ),
    (Flow.ORDER, Stage.DELIVERY_DETAILS): frozenset(
        {
            (Flow.ORDER, Stage.CATALOGUE_SEARCH),
            (Flow.ORDER, Stage.QUANTITY),
            (Flow.ORDER, Stage.FULFILMENT_METHOD),
            (Flow.ORDER, Stage.CUSTOMER_DETAILS),
            (Flow.ORDER, Stage.ORDER_REVIEW),
        }
    ),
    (Flow.ORDER, Stage.CUSTOMER_DETAILS): frozenset(
        {
            (Flow.ORDER, Stage.CATALOGUE_SEARCH),
            (Flow.ORDER, Stage.QUANTITY),
            (Flow.ORDER, Stage.FULFILMENT_METHOD),
            (Flow.ORDER, Stage.DELIVERY_DETAILS),
            (Flow.ORDER, Stage.ORDER_REVIEW),
        }
    ),
    (Flow.ORDER, Stage.ORDER_REVIEW): frozenset(
        {
            (Flow.ORDER, Stage.CATALOGUE_SEARCH),
            (Flow.ORDER, Stage.QUANTITY),
            (Flow.ORDER, Stage.FULFILMENT_METHOD),
            (Flow.ORDER, Stage.DELIVERY_DETAILS),
            (Flow.ORDER, Stage.CUSTOMER_DETAILS),
            (Flow.ORDER, Stage.CUSTOMER_CONFIRMATION),
            (Flow.ORDER, Stage.SUBMITTING),
        }
    ),
    (Flow.ORDER, Stage.CUSTOMER_CONFIRMATION): frozenset(
        {
            (Flow.ORDER, Stage.CATALOGUE_SEARCH),
            (Flow.ORDER, Stage.QUANTITY),
            (Flow.ORDER, Stage.FULFILMENT_METHOD),
            (Flow.ORDER, Stage.DELIVERY_DETAILS),
            (Flow.ORDER, Stage.CUSTOMER_DETAILS),
            (Flow.ORDER, Stage.ORDER_REVIEW),
            (Flow.ORDER, Stage.SUBMITTING),
        }
    ),
    (Flow.ORDER, Stage.SUBMITTING): frozenset(
        {
            (Flow.ORDER, Stage.ORDER_REVIEW),
            (Flow.ORDER, Stage.SUBMITTED),
        }
    ),
    (Flow.ORDER, Stage.SUBMITTED): frozenset({(Flow.IDLE, Stage.RESOLVED)}),
    (Flow.BOOKING, Stage.SERVICE_SELECTION): frozenset({(Flow.BOOKING, Stage.PREFERRED_DATE)}),
    (Flow.BOOKING, Stage.PREFERRED_DATE): frozenset(
        {
            (Flow.BOOKING, Stage.SERVICE_SELECTION),
            (Flow.BOOKING, Stage.TIME_SELECTION),
        }
    ),
    (Flow.BOOKING, Stage.TIME_SELECTION): frozenset(
        {
            (Flow.BOOKING, Stage.SERVICE_SELECTION),
            (Flow.BOOKING, Stage.PREFERRED_DATE),
            (Flow.BOOKING, Stage.STAFF_SELECTION),
            (Flow.BOOKING, Stage.CUSTOMER_DETAILS),
        }
    ),
    (Flow.BOOKING, Stage.STAFF_SELECTION): frozenset(
        {
            (Flow.BOOKING, Stage.SERVICE_SELECTION),
            (Flow.BOOKING, Stage.PREFERRED_DATE),
            (Flow.BOOKING, Stage.TIME_SELECTION),
            (Flow.BOOKING, Stage.CUSTOMER_DETAILS),
        }
    ),
    (Flow.BOOKING, Stage.CUSTOMER_DETAILS): frozenset(
        {
            (Flow.BOOKING, Stage.SERVICE_SELECTION),
            (Flow.BOOKING, Stage.PREFERRED_DATE),
            (Flow.BOOKING, Stage.TIME_SELECTION),
            (Flow.BOOKING, Stage.STAFF_SELECTION),
            (Flow.BOOKING, Stage.BOOKING_REVIEW),
        }
    ),
    (Flow.BOOKING, Stage.BOOKING_REVIEW): frozenset(
        {
            (Flow.BOOKING, Stage.SERVICE_SELECTION),
            (Flow.BOOKING, Stage.PREFERRED_DATE),
            (Flow.BOOKING, Stage.TIME_SELECTION),
            (Flow.BOOKING, Stage.STAFF_SELECTION),
            (Flow.BOOKING, Stage.CUSTOMER_DETAILS),
            (Flow.BOOKING, Stage.CUSTOMER_CONFIRMATION),
            (Flow.BOOKING, Stage.SUBMITTING),
        }
    ),
    (Flow.BOOKING, Stage.CUSTOMER_CONFIRMATION): frozenset(
        {
            (Flow.BOOKING, Stage.SERVICE_SELECTION),
            (Flow.BOOKING, Stage.PREFERRED_DATE),
            (Flow.BOOKING, Stage.TIME_SELECTION),
            (Flow.BOOKING, Stage.STAFF_SELECTION),
            (Flow.BOOKING, Stage.CUSTOMER_DETAILS),
            (Flow.BOOKING, Stage.BOOKING_REVIEW),
            (Flow.BOOKING, Stage.SUBMITTING),
        }
    ),
    (Flow.BOOKING, Stage.SUBMITTING): frozenset(
        {
            (Flow.BOOKING, Stage.BOOKING_REVIEW),
            (Flow.BOOKING, Stage.PREFERRED_DATE),
            (Flow.BOOKING, Stage.TIME_SELECTION),
            (Flow.BOOKING, Stage.STAFF_SELECTION),
            (Flow.BOOKING, Stage.SUBMITTED),
        }
    ),
    (Flow.BOOKING, Stage.SUBMITTED): frozenset({(Flow.IDLE, Stage.RESOLVED)}),
    (Flow.HANDOVER, Stage.WAITING_FOR_HUMAN): frozenset(
        {
            (Flow.HANDOVER, Stage.HUMAN_ACTIVE),
            (Flow.IDLE, Stage.START),
            (Flow.IDLE, Stage.CLOSED),
        }
    ),
    (Flow.HANDOVER, Stage.HUMAN_ACTIVE): frozenset(
        {
            (Flow.IDLE, Stage.START),
            (Flow.IDLE, Stage.CLOSED),
        }
    ),
}


class TransitionPolicy:
    """Authorize workflow actions and state changes."""

    def allowed_actions(self, context: TransitionContext) -> frozenset[IntentType]:
        if context.status in {SessionStatus.CLOSED, SessionStatus.EXPIRED}:
            return frozenset()
        if context.mode == ConversationMode.HUMAN:
            return _ALLOWED_ACTIONS.get((context.flow, context.stage), frozenset())

        actions = set(_ALLOWED_ACTIONS.get((context.flow, context.stage), frozenset()))
        actions.add(IntentType.CLARIFY)
        if context.flow not in {Flow.IDLE, Flow.HANDOVER}:
            actions.update(_GLOBAL_ACTIONS)
            actions.update(_SAFE_INTERRUPTS)
        return frozenset(actions)

    def require_action(self, context: TransitionContext, action: IntentType) -> None:
        if action not in self.allowed_actions(context):
            raise InvalidTransitionError(
                f"action {action.value!r} is not allowed from "
                f"{context.flow.value}/{context.stage.value}"
            )

    def require_target(self, context: TransitionContext, target: TransitionTarget) -> None:
        if context.status in {SessionStatus.CLOSED, SessionStatus.EXPIRED}:
            raise InvalidTransitionError("closed or expired sessions cannot transition")

        if target.flow == Flow.HANDOVER and target.stage == Stage.WAITING_FOR_HUMAN:
            if context.mode != ConversationMode.BOT:
                raise InvalidTransitionError("handover can only start from bot mode")
            if target.mode != ConversationMode.HUMAN or target.status != SessionStatus.PAUSED:
                raise InvalidTransitionError("handover must pause the bot in human mode")
            return

        if target.flow == Flow.IDLE and target.stage == Stage.CANCELLED:
            if context.flow in {Flow.IDLE, Flow.HANDOVER}:
                raise InvalidTransitionError("there is no active workflow to cancel")
            return

        if target.flow in {Flow.INFORMATION, Flow.FAQ} and context.flow in {
            Flow.CATALOGUE,
            Flow.ORDER,
            Flow.BOOKING,
        }:
            return

        allowed = _ALLOWED_TARGETS.get((context.flow, context.stage), frozenset())
        if (target.flow, target.stage) not in allowed:
            raise InvalidTransitionError(
                f"target {target.flow.value}/{target.stage.value} is not allowed from "
                f"{context.flow.value}/{context.stage.value}"
            )

        if target.flow == Flow.HANDOVER and target.mode != ConversationMode.HUMAN:
            raise InvalidTransitionError("handover targets require human mode")
        if target.stage == Stage.CLOSED and target.status != SessionStatus.CLOSED:
            raise InvalidTransitionError("closed stage requires closed status")

    def require_resume(self, context: TransitionContext, target: TransitionTarget) -> None:
        if context.flow not in {Flow.INFORMATION, Flow.FAQ, Flow.HANDOVER}:
            raise InvalidTransitionError("the current flow cannot resume a suspension")
        if target.flow in {Flow.IDLE, Flow.INFORMATION, Flow.FAQ, Flow.HANDOVER}:
            raise InvalidTransitionError("the suspended target is not a customer workflow")
        if target.mode != ConversationMode.BOT or target.status != SessionStatus.ACTIVE:
            raise InvalidTransitionError("a resumed workflow must return to active bot mode")
