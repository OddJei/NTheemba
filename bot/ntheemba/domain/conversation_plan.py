"""Reusable multi-workflow plans for compound customer requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from ntheemba.domain.capabilities import Capability


class PlannedWorkflowKind(StrEnum):
    """Business-neutral workflow kinds understood by Ntheemba."""

    CLIENT = "client"
    PRODUCT_ORDER = "product_order"
    APPOINTMENT = "appointment"
    LOYALTY = "loyalty"
    HANDOVER = "handover"


class PlannedWorkflowStatus(StrEnum):
    """Lifecycle state for one child workflow in a conversation plan."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class PlannedWorkflow:
    """One reusable child workflow in a compound request."""

    workflow_id: str
    kind: PlannedWorkflowKind
    required_capabilities: frozenset[Capability]
    status: PlannedWorkflowStatus = PlannedWorkflowStatus.PENDING
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.workflow_id.strip():
            raise ValueError("workflow_id must not be empty")
        if not self.required_capabilities:
            raise ValueError("required_capabilities must not be empty")
        object.__setattr__(self, "context", MappingProxyType(dict(self.context)))


@dataclass(frozen=True, slots=True)
class ConversationPlan:
    """Ordered child workflows collected from one customer request."""

    plan_id: str
    workflows: tuple[PlannedWorkflow, ...]

    def __post_init__(self) -> None:
        if not self.plan_id.strip():
            raise ValueError("plan_id must not be empty")
        if not self.workflows:
            raise ValueError("workflows must not be empty")
        workflow_ids = tuple(item.workflow_id for item in self.workflows)
        if len(workflow_ids) != len(set(workflow_ids)):
            raise ValueError("workflow IDs must be unique")

    @property
    def required_capabilities(self) -> frozenset[Capability]:
        """Return the union required by every child workflow."""

        return frozenset(
            capability
            for workflow in self.workflows
            for capability in workflow.required_capabilities
        )

    def missing_capabilities(
        self,
        enabled: frozenset[Capability],
    ) -> frozenset[Capability]:
        """Return capabilities preventing this plan from running."""

        return self.required_capabilities.difference(enabled)
