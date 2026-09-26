"""Reference Standard and Serah adapter operation boundaries."""

from __future__ import annotations

from collections.abc import Mapping

from ntheemba.adapters.tradeflow.contract import (
    InMemoryTradeFlowContractAdapter,
    OperationHandler,
)
from ntheemba.domain.tradeflow_contract import TradeFlowOperation


_STANDARD_OPERATIONS = frozenset(
    {
        TradeFlowOperation.BUSINESS_GET_PROFILE,
        TradeFlowOperation.BUSINESS_GET_HOURS,
        TradeFlowOperation.FAQ_SEARCH,
        TradeFlowOperation.CATALOGUE_SEARCH_PRODUCTS,
        TradeFlowOperation.CATALOGUE_GET_PRODUCT,
        TradeFlowOperation.INVENTORY_GET_PUBLIC_AVAILABILITY,
        TradeFlowOperation.ORDER_VALIDATE,
        TradeFlowOperation.ORDER_CREATE_REQUEST,
        TradeFlowOperation.ORDER_GET_REQUEST_STATUS,
        TradeFlowOperation.FULFILMENT_VALIDATE_DELIVERY,
        TradeFlowOperation.FULFILMENT_VALIDATE_COLLECTION,
        TradeFlowOperation.HANDOVER_CREATE_REQUEST,
    }
)

_SERAHS_OPERATIONS = frozenset(
    {
        *_STANDARD_OPERATIONS,
        TradeFlowOperation.CLIENT_FIND_BY_PHONE,
        TradeFlowOperation.CLIENT_GET_MINIMAL_PROFILE,
        TradeFlowOperation.CLIENT_CREATE,
        TradeFlowOperation.CLIENT_UPDATE_MINIMAL_PROFILE,
        TradeFlowOperation.CATALOGUE_SEARCH_SERVICES,
        TradeFlowOperation.CATALOGUE_GET_SERVICE,
        TradeFlowOperation.APPOINTMENT_CHECK_AVAILABILITY,
        TradeFlowOperation.APPOINTMENT_GET_ALTERNATIVES,
        TradeFlowOperation.APPOINTMENT_CREATE_REQUEST,
        TradeFlowOperation.APPOINTMENT_RESCHEDULE_REQUEST,
        TradeFlowOperation.APPOINTMENT_CANCEL_REQUEST,
        TradeFlowOperation.LOYALTY_GET_STATUS,
        TradeFlowOperation.LOYALTY_GET_PROGRESS,
    }
)


class StandardTradeFlowReferenceAdapter(InMemoryTradeFlowContractAdapter):
    """Reference boundary for the standard products/orders edition."""

    def __init__(
        self,
        *,
        business_id: str,
        handlers: Mapping[TradeFlowOperation, OperationHandler],
    ) -> None:
        unsupported = set(handlers).difference(_STANDARD_OPERATIONS)
        if unsupported:
            names = ", ".join(sorted(item.value for item in unsupported))
            raise ValueError(f"standard adapter cannot expose: {names}")
        super().__init__(business_id=business_id, handlers=handlers)


class SerahsTradeFlowReferenceAdapter(InMemoryTradeFlowContractAdapter):
    """Reference translator for Serah's customised TradeFlow edition."""

    def __init__(
        self,
        *,
        business_id: str,
        handlers: Mapping[TradeFlowOperation, OperationHandler],
    ) -> None:
        unsupported = set(handlers).difference(_SERAHS_OPERATIONS)
        if unsupported:
            names = ", ".join(sorted(item.value for item in unsupported))
            raise ValueError(f"Serah adapter cannot expose: {names}")
        super().__init__(business_id=business_id, handlers=handlers)
