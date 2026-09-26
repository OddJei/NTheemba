"""Build reusable workflow plans without hard-coding business names."""

from __future__ import annotations

from dataclasses import dataclass

from ntheemba.domain.capabilities import Capability
from ntheemba.domain.conversation_plan import (
    ConversationPlan,
    PlannedWorkflow,
    PlannedWorkflowKind,
)


@dataclass(frozen=True, slots=True)
class CompoundRequest:
    """Structured workflow wishes extracted from one customer message."""

    needs_client: bool = False
    wants_product_order: bool = False
    wants_appointment: bool = False
    wants_loyalty: bool = False
    wants_handover: bool = False


class ConversationPlanBuilder:
    """Translate requested actions into canonical Ntheemba workflows."""

    def build(self, plan_id: str, request: CompoundRequest) -> ConversationPlan:
        workflows: list[PlannedWorkflow] = []
        if request.needs_client:
            workflows.append(
                PlannedWorkflow(
                    workflow_id=f"{plan_id}:client",
                    kind=PlannedWorkflowKind.CLIENT,
                    required_capabilities=frozenset({Capability.CLIENT_IDENTIFY}),
                )
            )
        if request.wants_appointment:
            workflows.append(
                PlannedWorkflow(
                    workflow_id=f"{plan_id}:appointment",
                    kind=PlannedWorkflowKind.APPOINTMENT,
                    required_capabilities=frozenset(
                        {
                            Capability.SERVICE_CATALOGUE,
                            Capability.APPOINTMENT_CREATE,
                        }
                    ),
                )
            )
        if request.wants_product_order:
            workflows.append(
                PlannedWorkflow(
                    workflow_id=f"{plan_id}:product-order",
                    kind=PlannedWorkflowKind.PRODUCT_ORDER,
                    required_capabilities=frozenset(
                        {
                            Capability.PRODUCT_CATALOGUE,
                            Capability.PRODUCT_ORDER,
                        }
                    ),
                )
            )
        if request.wants_loyalty:
            workflows.append(
                PlannedWorkflow(
                    workflow_id=f"{plan_id}:loyalty",
                    kind=PlannedWorkflowKind.LOYALTY,
                    required_capabilities=frozenset({Capability.LOYALTY_READ}),
                )
            )
        if request.wants_handover:
            workflows.append(
                PlannedWorkflow(
                    workflow_id=f"{plan_id}:handover",
                    kind=PlannedWorkflowKind.HANDOVER,
                    required_capabilities=frozenset({Capability.HANDOVER}),
                )
            )
        return ConversationPlan(plan_id=plan_id, workflows=tuple(workflows))
