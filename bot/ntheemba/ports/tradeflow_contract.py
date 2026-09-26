"""Generic adapter port for the Ntheemba-owned TradeFlow contract."""

from __future__ import annotations

from typing import Protocol

from ntheemba.domain.tradeflow_contract import TradeFlowRequest, TradeFlowResponse


class TradeFlowContractAdapter(Protocol):
    """Execute only versioned operations known to Ntheemba."""

    def supports_operation(self, operation: object) -> bool:
        """Return whether this adapter can execute one known operation."""

    async def execute(self, request: TradeFlowRequest) -> TradeFlowResponse:
        """Execute one validated request for the exact business tenant."""
