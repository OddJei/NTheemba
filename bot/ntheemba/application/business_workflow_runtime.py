"""Unified deterministic entry point for business-owned workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ntheemba.application.runtime_context import BusinessExecutionContext
from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowResult,
    WorkflowRouterPort,
)
from ntheemba.domain.intents import Intent
from ntheemba.domain.session import Session


class BusinessWorkflowOrigin(StrEnum):
    """Trusted origin of a business workflow execution."""

    BUSINESS_CHANNEL = "business_channel"
    MARKETPLACE_HANDOFF = "marketplace_handoff"


class BusinessWorkflowEntryError(ValueError):
    """Raised when a session and trusted business context do not align."""


@dataclass(slots=True)
class BusinessWorkflowRuntime:
    """Route all business workflow families through one guarded runtime boundary."""

    router: WorkflowRouterPort

    async def route(
        self,
        *,
        execution_context: BusinessExecutionContext,
        session: Session,
        intent: Intent,
        request_id: str,
        message_id: str,
        origin: BusinessWorkflowOrigin = BusinessWorkflowOrigin.BUSINESS_CHANNEL,
        channel_instance_id: str = "",
        mutation_idempotency_key: str = "",
    ) -> WorkflowResult:
        business_id = execution_context.business.business_id
        if session.business_id != business_id:
            raise BusinessWorkflowEntryError(
                "session business does not match the trusted execution context"
            )
        if not request_id.strip() or not message_id.strip():
            raise BusinessWorkflowEntryError("request_id and message_id are required")
        if not session.customer_id.strip():
            raise BusinessWorkflowEntryError("session customer_id is required")
        return await self.router.route(
            WorkflowContext(
                session=session,
                intent=intent,
                business_id=business_id,
                customer_id=session.customer_id,
                request_id=request_id.strip(),
                message_id=message_id.strip(),
                capabilities=execution_context.capabilities,
                channel_instance_id=channel_instance_id.strip(),
                business_context=execution_context,
                workflow_origin=origin.value,
                mutation_idempotency_key=mutation_idempotency_key.strip(),
            )
        )
