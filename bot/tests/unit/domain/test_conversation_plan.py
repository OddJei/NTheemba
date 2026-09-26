"""Tests for reusable compound conversation plans."""

from ntheemba.application.conversation_planner import (
    CompoundRequest,
    ConversationPlanBuilder,
)
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.conversation_plan import PlannedWorkflowKind


def test_service_and_product_request_builds_two_reusable_child_workflows() -> None:
    plan = ConversationPlanBuilder().build(
        "plan-1",
        CompoundRequest(
            needs_client=True,
            wants_appointment=True,
            wants_product_order=True,
        ),
    )

    assert tuple(item.kind for item in plan.workflows) == (
        PlannedWorkflowKind.CLIENT,
        PlannedWorkflowKind.APPOINTMENT,
        PlannedWorkflowKind.PRODUCT_ORDER,
    )
    assert plan.required_capabilities == frozenset(
        {
            Capability.CLIENT_IDENTIFY,
            Capability.SERVICE_CATALOGUE,
            Capability.APPOINTMENT_CREATE,
            Capability.PRODUCT_CATALOGUE,
            Capability.PRODUCT_ORDER,
        }
    )


def test_compound_plan_reports_business_missing_capabilities() -> None:
    plan = ConversationPlanBuilder().build(
        "plan-2",
        CompoundRequest(wants_appointment=True, wants_product_order=True),
    )

    missing = plan.missing_capabilities(
        frozenset({Capability.PRODUCT_CATALOGUE, Capability.PRODUCT_ORDER})
    )

    assert missing == frozenset(
        {Capability.SERVICE_CATALOGUE, Capability.APPOINTMENT_CREATE}
    )
