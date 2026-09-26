"""Human-handover workflow and trusted staff-control operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowEvent,
    WorkflowHandler,
    WorkflowResult,
)
from ntheemba.domain.enums import (
    Flow,
    IntentType,
)
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import TransitionPolicy
from ntheemba.services.response_builder import ResponseBuilder

_CUSTOMER_FLOWS = frozenset({Flow.CATALOGUE, Flow.ORDER, Flow.BOOKING})
_ROUTED_INTENTS = frozenset(
    {
        IntentType.HANDOVER,
        IntentType.RESUME_BOT,
        IntentType.CLOSE_SESSION,
    }
)


class UnsupportedHandoverIntentError(ValueError):
    """Raised when the handover workflow receives an intent it does not own."""


@dataclass(frozen=True, slots=True)
class HandoverWorkflowConfig:
    """Behavior switches for human handover."""

    preserve_customer_workflow: bool = True


class HandoverWorkflow:
    """Pause automation, support staff takeover, resume, or close a session."""

    def __init__(
        self,
        *,
        responses: ResponseBuilder,
        transition_policy: TransitionPolicy | None = None,
        config: HandoverWorkflowConfig | None = None,
    ) -> None:
        self.responses = responses
        self.transition_policy = transition_policy or TransitionPolicy()
        self.config = config or HandoverWorkflowConfig()

    async def handle(self, context: WorkflowContext) -> WorkflowResult:
        """Handle customer/system handover, bot-resume, and close intents."""

        if context.intent.type not in _ROUTED_INTENTS:
            raise UnsupportedHandoverIntentError(
                f"handover workflow does not handle {context.intent.type.value!r}"
            )

        if context.intent.type == IntentType.HANDOVER:
            return self._request_handover(context.session)
        if context.intent.type == IntentType.RESUME_BOT:
            return self._resume_bot(context.session)
        return self._close_session(context.session)

    def activate_human(self, session: Session) -> WorkflowResult:
        """Trusted staff operation marking that a person accepted the handover."""

        previous_stage = session.stage
        session.mark_human_active(self.transition_policy)
        return WorkflowResult(
            replies=(self.responses.human_active(),),
            events=(
                WorkflowEvent(
                    event_type="handover.human_active",
                    data={
                        "previous_stage": previous_stage.value,
                        "handover_status": session.handover_status.value,
                    },
                ),
            ),
        )

    def _request_handover(self, session: Session) -> WorkflowResult:
        previous_flow = session.flow
        previous_stage = session.stage
        preserve = self.config.preserve_customer_workflow and previous_flow in _CUSTOMER_FLOWS

        session.request_handover(
            self.transition_policy,
            preserve_workflow=preserve,
        )

        return WorkflowResult(
            replies=(self.responses.handover_requested(),),
            events=(
                WorkflowEvent(
                    event_type="handover.requested",
                    data={
                        "previous_flow": previous_flow.value,
                        "previous_stage": previous_stage.value,
                        "workflow_preserved": session.suspended_state is not None,
                        "handover_status": session.handover_status.value,
                    },
                ),
            ),
        )

    def _resume_bot(self, session: Session) -> WorkflowResult:
        previous_stage = session.stage
        had_suspended_workflow = session.suspended_state is not None

        session.resume_bot(self.transition_policy)

        pending_prompt = (
            session.pending_question.prompt if session.pending_question is not None else None
        )
        return WorkflowResult(
            replies=(self.responses.bot_resumed(pending_prompt),),
            events=(
                WorkflowEvent(
                    event_type="handover.bot_resumed",
                    data={
                        "previous_stage": previous_stage.value,
                        "restored_workflow": had_suspended_workflow,
                        "flow": session.flow.value,
                        "stage": session.stage.value,
                        "pending_question_restored": pending_prompt is not None,
                        "handover_status": session.handover_status.value,
                    },
                ),
            ),
        )

    def _close_session(self, session: Session) -> WorkflowResult:
        session.authorize(self.transition_policy, IntentType.CLOSE_SESSION)
        previous_stage = session.stage
        session.close()

        return WorkflowResult(
            replies=(self.responses.conversation_closed(),),
            events=(
                WorkflowEvent(
                    event_type="handover.conversation_closed",
                    data={
                        "previous_stage": previous_stage.value,
                        "status": session.status.value,
                        "handover_status": session.handover_status.value,
                    },
                ),
            ),
        )


def build_handover_routes(
    workflow: WorkflowHandler,
) -> Mapping[IntentType, WorkflowHandler]:
    """Return WorkflowRouter registrations owned by this workflow."""

    return {
        IntentType.HANDOVER: workflow,
        IntentType.RESUME_BOT: workflow,
        IntentType.CLOSE_SESSION: workflow,
    }
