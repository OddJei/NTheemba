"""Reusable loyalty-status workflow owned by Ntheemba."""

from __future__ import annotations

from typing import Protocol

from ntheemba.application.customer_bridge import CustomerBridgeService
from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowEvent,
    WorkflowReply,
    WorkflowResult,
)
from ntheemba.domain.customers import LoyaltyStatus


class LoyaltyTradeFlowPort(Protocol):
    """Read business-calculated loyalty without copying the rules into Ntheemba."""

    async def get_loyalty_status(
        self,
        business_id: str,
        client_id: str,
    ) -> LoyaltyStatus | None:
        """Return a business-calculated loyalty result."""


class LoyaltyWorkflow:
    """Resolve a business client and explain its TradeFlow loyalty result."""

    def __init__(
        self,
        *,
        customers: CustomerBridgeService,
        tradeflow: LoyaltyTradeFlowPort,
    ) -> None:
        self.customers = customers
        self.tradeflow = tradeflow

    async def handle(self, context: WorkflowContext) -> WorkflowResult:
        link = await self.customers.resolve_business_client(
            business_id=context.business_id,
            customer_id=context.customer_id,
        )
        if link is None:
            return WorkflowResult(
                replies=(
                    WorkflowReply.text_reply(
                        "I cannot find a client profile for this business yet. "
                        "Complete a booking or order with your name and phone number first."
                    ),
                ),
                events=(WorkflowEvent("loyalty.client_not_found"),),
            )
        status = await self.tradeflow.get_loyalty_status(
            context.business_id,
            link.external_client_id,
        )
        if status is None:
            return WorkflowResult(
                replies=(
                    WorkflowReply.text_reply(
                        "Your client profile is recognised, but this business has no "
                        "loyalty result available yet."
                    ),
                ),
                events=(WorkflowEvent("loyalty.status_unavailable"),),
            )
        parts = [
            f"Your loyalty status is {status.tier} with {status.points} points."
        ]
        if status.next_tier and status.points_needed is not None:
            parts.append(
                f"You need {status.points_needed} more points to reach {status.next_tier}."
            )
        if status.reward_description:
            parts.append(status.reward_description)
        elif status.discount_percent > 0:
            scope = f" on {status.discount_scope}" if status.discount_scope else ""
            parts.append(f"Your current discount is {status.discount_percent}%{scope}.")
        return WorkflowResult(
            replies=(WorkflowReply.text_reply(" ".join(parts)),),
            events=(
                WorkflowEvent(
                    "loyalty.status_returned",
                    {"tier": status.tier, "points": str(status.points)},
                ),
            ),
        )
