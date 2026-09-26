"""Business information, opening-hours, and FAQ workflow."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowEvent,
    WorkflowHandler,
    WorkflowReply,
    WorkflowResult,
)
from ntheemba.domain.enums import Flow, IntentType, MessageRole, Stage
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import TransitionPolicy
from ntheemba.ports.tradeflow import TradeFlowPort
from ntheemba.services.response_builder import ResponseBuilder

_SUPPORTED_INTENTS: Final[frozenset[IntentType]] = frozenset(
    {
        IntentType.BUSINESS_INFO,
        IntentType.BUSINESS_HOURS,
        IntentType.FAQ,
    }
)
_CUSTOMER_FLOWS: Final[frozenset[Flow]] = frozenset(
    {
        Flow.CATALOGUE,
        Flow.ORDER,
        Flow.BOOKING,
    }
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class UnsupportedInformationIntentError(ValueError):
    """Raised when the workflow receives an intent it does not own."""


@dataclass(frozen=True, slots=True)
class InformationWorkflowConfig:
    """Limits and wording inputs for the information workflow."""

    faq_result_limit: int = 5

    def __post_init__(self) -> None:
        if self.faq_result_limit <= 0:
            raise ValueError("faq_result_limit must be greater than zero")


class InformationWorkflow:
    """Serve public business facts and safely resume interrupted workflows."""

    def __init__(
        self,
        *,
        tradeflow: TradeFlowPort,
        responses: ResponseBuilder,
        transition_policy: TransitionPolicy | None = None,
        clock: Callable[[], datetime] = _utc_now,
        config: InformationWorkflowConfig | None = None,
    ) -> None:
        self.tradeflow = tradeflow
        self.responses = responses
        self.transition_policy = transition_policy or TransitionPolicy()
        self.clock = clock
        self.config = config or InformationWorkflowConfig()

    async def handle(self, context: WorkflowContext) -> WorkflowResult:
        """Handle one approved business-info, hours, or FAQ intent."""

        if context.intent.type not in _SUPPORTED_INTENTS:
            raise UnsupportedInformationIntentError(
                f"information workflow does not handle {context.intent.type.value!r}"
            )

        target_flow, target_stage = self._target_state(context.intent.type)
        interrupted = self._is_safe_interruption(context)
        self._enter_information_state(
            context.session,
            target_flow=target_flow,
            target_stage=target_stage,
            interrupted=interrupted,
        )

        try:
            replies, events = await self._execute(context)
        except (ConnectionError, TimeoutError) as error:
            replies = (
                self.responses.dependency_failure(
                    retryable=True,
                    action_name=self._action_name(context.intent.type),
                ),
            )
            events = (
                WorkflowEvent(
                    event_type="information.dependency_failed",
                    data={
                        "intent": context.intent.type.value,
                        "retryable": True,
                        "error_type": type(error).__name__,
                        "safe_interruption": interrupted,
                    },
                ),
            )
        except LookupError as error:
            replies = (
                self.responses.dependency_failure(
                    retryable=False,
                    action_name=self._action_name(context.intent.type),
                ),
            )
            events = (
                WorkflowEvent(
                    event_type="information.dependency_failed",
                    data={
                        "intent": context.intent.type.value,
                        "retryable": False,
                        "error_type": type(error).__name__,
                        "safe_interruption": interrupted,
                    },
                ),
            )

        completion_replies, completion_events = self._complete_information_state(
            context.session,
            interrupted=interrupted,
        )
        return WorkflowResult(
            replies=(*replies, *completion_replies),
            events=(*events, *completion_events),
        )

    async def _execute(
        self,
        context: WorkflowContext,
    ) -> tuple[tuple[WorkflowReply, ...], tuple[WorkflowEvent, ...]]:
        if context.intent.type == IntentType.BUSINESS_INFO:
            info = await self.tradeflow.get_business_information(context.business_id)
            return (
                (self.responses.business_information(info),),
                (
                    WorkflowEvent(
                        event_type="information.business_profile_served",
                        data={
                            "safe_interruption": self._is_safe_interruption(context),
                        },
                    ),
                ),
            )

        if context.intent.type == IntentType.BUSINESS_HOURS:
            at = self.clock()
            if at.tzinfo is None:
                raise ValueError("information workflow clock must be timezone-aware")
            hours = await self.tradeflow.get_business_hours(
                context.business_id,
                at=at,
            )
            return (
                (self.responses.business_hours(hours),),
                (
                    WorkflowEvent(
                        event_type="information.business_hours_served",
                        data={
                            "safe_interruption": self._is_safe_interruption(context),
                            "special_closure": hours.special_closure,
                            "is_open": hours.is_open,
                        },
                    ),
                ),
            )

        query = (context.intent.entities.query or context.intent.entities.raw_text).strip()
        if not query:
            return (
                (self.responses.clarification("What would you like to know about the business?"),),
                (
                    WorkflowEvent(
                        event_type="information.faq_query_missing",
                        data={
                            "safe_interruption": self._is_safe_interruption(context),
                        },
                    ),
                ),
            )

        answers = await self.tradeflow.search_faqs(
            context.business_id,
            query,
            limit=self.config.faq_result_limit,
        )
        if not answers:
            return (
                (self.responses.faq_not_found(),),
                (
                    WorkflowEvent(
                        event_type="information.faq_not_found",
                        data={
                            "query_length": len(query),
                            "safe_interruption": self._is_safe_interruption(context),
                        },
                    ),
                ),
            )

        selected = answers[0]
        return (
            (self.responses.faq_answer(selected),),
            (
                WorkflowEvent(
                    event_type="information.faq_answered",
                    data={
                        "query_length": len(query),
                        "candidate_count": len(answers),
                        "safe_interruption": self._is_safe_interruption(context),
                    },
                ),
            ),
        )

    def _enter_information_state(
        self,
        session: Session,
        *,
        target_flow: Flow,
        target_stage: Stage,
        interrupted: bool,
    ) -> None:
        if interrupted:
            session.suspend_for_side_question(
                self.transition_policy,
                flow=target_flow,
                stage=target_stage,
            )
            return

        if session.flow == Flow.IDLE and session.stage in {
            Stage.CANCELLED,
            Stage.RESOLVED,
        }:
            session.transition_to(
                self.transition_policy,
                Flow.IDLE,
                Stage.START,
            )

        if session.flow == target_flow and session.stage == target_stage:
            return

        session.transition_to(
            self.transition_policy,
            target_flow,
            target_stage,
        )

    def _complete_information_state(
        self,
        session: Session,
        *,
        interrupted: bool,
    ) -> tuple[tuple[WorkflowReply, ...], tuple[WorkflowEvent, ...]]:
        if interrupted:
            session.resume_suspended(self.transition_policy)
            prompt = (
                session.pending_question.prompt if session.pending_question is not None else None
            )
            return (
                (self.responses.workflow_resumed(prompt),),
                (
                    WorkflowEvent(
                        event_type="information.previous_workflow_resumed",
                        data={
                            "flow": session.flow.value,
                            "stage": session.stage.value,
                            "pending_question_restored": prompt is not None,
                        },
                    ),
                ),
            )

        session.transition_to(
            self.transition_policy,
            Flow.IDLE,
            Stage.START,
        )
        return (), ()

    @staticmethod
    def _target_state(intent_type: IntentType) -> tuple[Flow, Stage]:
        if intent_type == IntentType.FAQ:
            return Flow.FAQ, Stage.FAQ_SEARCH
        return Flow.INFORMATION, Stage.INFORMATION_LOOKUP

    @staticmethod
    def _is_safe_interruption(context: WorkflowContext) -> bool:
        return (
            context.intent.role == MessageRole.SAFE_INTERRUPTION
            and context.session.flow in _CUSTOMER_FLOWS
        )

    @staticmethod
    def _action_name(intent_type: IntentType) -> str:
        names = {
            IntentType.BUSINESS_INFO: "the business information request",
            IntentType.BUSINESS_HOURS: "the opening-hours request",
            IntentType.FAQ: "the business question",
        }
        return names[intent_type]


def build_information_routes(
    workflow: WorkflowHandler,
) -> Mapping[IntentType, WorkflowHandler]:
    """Return the WorkflowRouter registrations owned by this workflow."""

    return {
        IntentType.BUSINESS_INFO: workflow,
        IntentType.BUSINESS_HOURS: workflow,
        IntentType.FAQ: workflow,
    }
