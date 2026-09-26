"""Flow-aware workflow dispatch shared by real and developer runtime composition."""

from __future__ import annotations

from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowHandler,
    WorkflowResult,
)
from ntheemba.domain.enums import Flow, IntentType
from ntheemba.services.response_builder import ResponseBuilder


class FlowAwareWorkflowHandler:
    """Dispatch intents using both the interpreted action and active session flow."""

    def __init__(
        self,
        *,
        information: WorkflowHandler,
        catalogue: WorkflowHandler,
        order: WorkflowHandler,
        booking: WorkflowHandler,
        loyalty: WorkflowHandler,
        handover: WorkflowHandler,
        responses: ResponseBuilder,
    ) -> None:
        self._information = information
        self._catalogue = catalogue
        self._order = order
        self._booking = booking
        self._loyalty = loyalty
        self._handover = handover
        self._responses = responses

    async def handle(self, context: WorkflowContext) -> WorkflowResult:
        intent_type = context.intent.type
        if intent_type in {
            IntentType.BUSINESS_INFO,
            IntentType.BUSINESS_HOURS,
            IntentType.FAQ,
        }:
            return await self._information.handle(context)
        if intent_type in {
            IntentType.HANDOVER,
            IntentType.RESUME_BOT,
            IntentType.CLOSE_SESSION,
        }:
            return await self._handover.handle(context)
        if intent_type == IntentType.LOYALTY_STATUS:
            return await self._loyalty.handle(context)
        if intent_type == IntentType.START_BOOKING or context.session.flow == Flow.BOOKING:
            return await self._booking.handle(context)
        if intent_type == IntentType.START_ORDER or context.session.flow == Flow.ORDER:
            return await self._order.handle(context)
        if intent_type in {IntentType.CATALOGUE_SEARCH, IntentType.SELECT_ITEM}:
            return await self._catalogue.handle(context)
        if intent_type in {IntentType.CLARIFY, IntentType.UNKNOWN, IntentType.CONTINUE}:
            return WorkflowResult(
                replies=(
                    self._responses.clarification(
                        "Tell me what you would like to know, buy, book, or check about loyalty."
                    ),
                )
            )
        if intent_type in {
            IntentType.PROVIDE_QUANTITY,
            IntentType.PROVIDE_FULFILMENT_METHOD,
            IntentType.PROVIDE_DELIVERY_DETAILS,
            IntentType.PROVIDE_CUSTOMER_DETAILS,
            IntentType.CONFIRM,
            IntentType.CORRECT,
            IntentType.CANCEL,
        }:
            return await self._order.handle(context)
        raise LookupError(f"no workflow is configured for {intent_type.value}")
