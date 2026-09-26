"""Tests for the Ntheemba-owned canonical capability catalogue."""

from ntheemba.domain.capabilities import Capability, CapabilityCatalogue
from ntheemba.domain.tradeflow_contract import (
    TradeFlowOperation,
    UnknownTradeFlowOperationError,
    capability_for_operation,
    parse_tradeflow_operation,
)


def test_catalogue_accepts_known_and_rejects_unknown_declarations() -> None:
    catalogue = CapabilityCatalogue.canonical()

    assert catalogue.version == "ntheemba-capabilities-v1"

    result = catalogue.validate_declarations(
        [Capability.PRODUCT_ORDER.value, "salon.vip_chat", Capability.LOYALTY_READ.value]
    )

    assert result.supported == frozenset(
        {Capability.PRODUCT_ORDER, Capability.LOYALTY_READ}
    )
    assert result.unknown == frozenset({"salon.vip_chat"})
    assert catalogue.contains("salon.vip_chat") is False


def test_tradeflow_operations_are_owned_and_mapped_by_ntheemba() -> None:
    operation = parse_tradeflow_operation("appointment.create_request")

    assert operation == TradeFlowOperation.APPOINTMENT_CREATE_REQUEST
    assert capability_for_operation(operation) == Capability.APPOINTMENT_CREATE


def test_unknown_tradeflow_operation_is_never_auto_enabled() -> None:
    try:
        parse_tradeflow_operation("salon.create_vip_membership")
    except UnknownTradeFlowOperationError as error:
        assert "not known by Ntheemba" in str(error)
    else:
        raise AssertionError("unknown operation should have been rejected")
