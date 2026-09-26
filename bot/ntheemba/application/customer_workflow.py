"""Decorator that links confirmed customer details to eligible businesses."""

from __future__ import annotations

from ntheemba.application.customer_bridge import CustomerBridgeService
from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowEvent,
    WorkflowHandler,
    WorkflowResult,
)
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.enums import IntentType


class CustomerAwareWorkflowHandler:
    """Create a minimal business-client link after customer details are confirmed."""

    def __init__(self, inner: WorkflowHandler, *, customers: CustomerBridgeService) -> None:
        self.inner = inner
        self.customers = customers

    async def handle(self, context: WorkflowContext) -> WorkflowResult:
        result = await self.inner.handle(context)
        if (
            context.intent.type != IntentType.PROVIDE_CUSTOMER_DETAILS
            or Capability.CLIENT_CREATE not in context.capabilities
        ):
            return result
        name = ""
        if context.session.order_draft is not None:
            name = context.session.order_draft.customer_name or ""
        if context.session.booking_draft is not None:
            name = context.session.booking_draft.customer_name or name
        if len(name.strip()) < 2:
            return result
        link = await self.customers.ensure_business_client(
            business_id=context.business_id,
            customer_id=context.customer_id,
            display_name=name,
            idempotency_key=f"{context.business_id}:{context.customer_id}:client",
        )
        return WorkflowResult(
            replies=result.replies,
            events=(
                *result.events,
                WorkflowEvent(
                    "client.linked",
                    {"external_client_id": link.external_client_id},
                ),
            ),
            close_session=result.close_session,
        )
