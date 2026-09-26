"""Tests for capability-controlled TradeFlow contract execution."""

from datetime import UTC, datetime

import pytest
from ntheemba.adapters.businesses import InMemoryUnsupportedDeclarationSink
from ntheemba.adapters.tradeflow import (
    CapabilityControlledTradeFlowAdapter,
    NtheembaTradeFlowIngress,
)
from ntheemba.adapters.tradeflow.contract import InMemoryTradeFlowContractAdapter
from ntheemba.adapters.tradeflow.reference import StandardTradeFlowReferenceAdapter
from ntheemba.domain.business import (
    BusinessChannel,
    BusinessIntegration,
    BusinessProfile,
    ResolvedBusinessContext,
)
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.tradeflow_contract import TradeFlowOperation, TradeFlowRequest


async def _ok(_request: TradeFlowRequest) -> dict[str, str]:
    return {"status": "ok"}


@pytest.mark.asyncio
async def test_operation_requires_the_business_enabled_capability() -> None:
    profile = BusinessProfile(
        "amac",
        "AMAC",
        "tradeflow_standard",
        frozenset({Capability.PRODUCT_ORDER.value}),
    )
    channel = BusinessChannel("wa-amac", "openwa", "amac", "+260970000001")
    context = ResolvedBusinessContext(
        profile,
        channel,
        frozenset({Capability.PRODUCT_ORDER}),
    )
    observations = InMemoryUnsupportedDeclarationSink()
    inner = InMemoryTradeFlowContractAdapter(
        business_id="amac",
        handlers={TradeFlowOperation.LOYALTY_GET_STATUS: _ok},
    )
    adapter = CapabilityControlledTradeFlowAdapter(
        context=context,
        inner=inner,
        observations=observations,
    )

    response = await adapter.execute(
        TradeFlowRequest(
            request_id="request-1",
            business_id="amac",
            operation=TradeFlowOperation.LOYALTY_GET_STATUS,
        )
    )

    assert response.ok is False
    assert response.error_code == "CAPABILITY_NOT_ENABLED"
    recorded = await observations.list_observations()
    assert recorded[0].value == TradeFlowOperation.LOYALTY_GET_STATUS.value
    assert recorded[0].observed_at <= datetime.now(UTC)


@pytest.mark.asyncio
async def test_operation_requires_configured_enabled_integration_before_call() -> None:
    profile = BusinessProfile(
        "serah",
        "Serah's Glow",
        "tradeflow_serahs",
        frozenset({Capability.APPOINTMENT_CREATE.value}),
    )
    channel = BusinessChannel("wa-serah", "openwa", "serah", "+260970000002")
    context = ResolvedBusinessContext(
        profile,
        channel,
        frozenset({Capability.APPOINTMENT_CREATE}),
    )
    inner = InMemoryTradeFlowContractAdapter(
        business_id="serah",
        handlers={TradeFlowOperation.APPOINTMENT_CHECK_AVAILABILITY: _ok},
    )
    adapter = CapabilityControlledTradeFlowAdapter(
        context=context,
        inner=inner,
        observations=InMemoryUnsupportedDeclarationSink(),
    )

    response = await adapter.execute(
        TradeFlowRequest(
            request_id="request-no-integration",
            business_id="serah",
            operation=TradeFlowOperation.APPOINTMENT_CHECK_AVAILABILITY,
            payload={"service_id": "svc-1", "date": "2026-08-23"},
        )
    )

    assert response.ok is False
    assert response.error_code == "INTEGRATION_NOT_CONFIGURED"
    assert inner.requests == []


@pytest.mark.asyncio
async def test_operation_requires_public_contract_inputs_before_call() -> None:
    capabilities = frozenset({Capability.APPOINTMENT_CREATE})
    profile = BusinessProfile(
        "serah",
        "Serah's Glow",
        "tradeflow_serahs",
        frozenset(capability.value for capability in capabilities),
    )
    channel = BusinessChannel("wa-serah", "openwa", "serah", "+260970000002")
    context = ResolvedBusinessContext(
        profile,
        channel,
        capabilities,
        integrations=(
            BusinessIntegration(
                "serah-tradeflow",
                "serah",
                "tradeflow_serahs",
                "https://tradeflow.local/serah",
                capabilities=frozenset(capability.value for capability in capabilities),
            ),
        ),
    )
    inner = InMemoryTradeFlowContractAdapter(
        business_id="serah",
        handlers={TradeFlowOperation.APPOINTMENT_CHECK_AVAILABILITY: _ok},
    )
    adapter = CapabilityControlledTradeFlowAdapter(
        context=context,
        inner=inner,
        observations=InMemoryUnsupportedDeclarationSink(),
    )

    response = await adapter.execute(
        TradeFlowRequest(
            request_id="request-missing-inputs",
            business_id="serah",
            operation=TradeFlowOperation.APPOINTMENT_CHECK_AVAILABILITY,
            payload={"service_id": "svc-1"},
        )
    )

    assert response.ok is False
    assert response.error_code == "INVALID_TRADEFLOW_REQUEST"
    assert "date" in response.error_message
    assert inner.requests == []


@pytest.mark.asyncio
async def test_unsupported_optional_operation_fails_without_inner_call() -> None:
    capabilities = frozenset({Capability.APPOINTMENT_RESCHEDULE})
    profile = BusinessProfile(
        "serah",
        "Serah's Glow",
        "tradeflow_serahs",
        frozenset(capability.value for capability in capabilities),
    )
    channel = BusinessChannel("wa-serah", "openwa", "serah", "+260970000002")
    context = ResolvedBusinessContext(
        profile,
        channel,
        capabilities,
        integrations=(
            BusinessIntegration(
                "serah-tradeflow",
                "serah",
                "tradeflow_serahs",
                "https://tradeflow.local/serah",
                capabilities=frozenset(capability.value for capability in capabilities),
            ),
        ),
    )
    observations = InMemoryUnsupportedDeclarationSink()
    inner = InMemoryTradeFlowContractAdapter(business_id="serah", handlers={})
    adapter = CapabilityControlledTradeFlowAdapter(
        context=context,
        inner=inner,
        observations=observations,
    )

    response = await adapter.execute(
        TradeFlowRequest(
            request_id="request-unsupported-optional",
            business_id="serah",
            operation=TradeFlowOperation.APPOINTMENT_RESCHEDULE_REQUEST,
            payload={"request_id": "BKG-1", "slot_id": "slot-2"},
            idempotency_key="reschedule-BKG-1",
        )
    )

    assert response.ok is False
    assert response.error_code == "OPERATION_NOT_IMPLEMENTED"
    assert inner.requests == []
    recorded = await observations.list_observations()
    assert recorded[0].value == TradeFlowOperation.APPOINTMENT_RESCHEDULE_REQUEST.value
    assert recorded[0].source == "adapter_capability_guard"


def test_standard_reference_adapter_rejects_service_methods() -> None:
    with pytest.raises(ValueError, match="standard adapter cannot expose"):
        StandardTradeFlowReferenceAdapter(
            business_id="harvest",
            handlers={TradeFlowOperation.APPOINTMENT_CREATE_REQUEST: _ok},
        )


@pytest.mark.asyncio
async def test_unknown_raw_tradeflow_method_is_rejected_and_observed() -> None:
    profile = BusinessProfile(
        "serahs",
        "Serah's Glow",
        "tradeflow_serahs",
        frozenset({Capability.LOYALTY_READ.value}),
    )
    channel = BusinessChannel("wa-serahs", "openwa", "serahs", "+260970000002")
    context = ResolvedBusinessContext(
        profile,
        channel,
        frozenset({Capability.LOYALTY_READ}),
    )
    observations = InMemoryUnsupportedDeclarationSink()
    inner = InMemoryTradeFlowContractAdapter(
        business_id="serahs",
        handlers={TradeFlowOperation.LOYALTY_GET_STATUS: _ok},
    )
    controlled = CapabilityControlledTradeFlowAdapter(
        context=context,
        inner=inner,
        observations=observations,
    )
    ingress = NtheembaTradeFlowIngress(
        context=context,
        adapter=controlled,
        observations=observations,
    )

    response = await ingress.execute_raw(
        request_id="request-unknown",
        business_id="serahs",
        operation="loyalty.calculate_secret_score",
    )

    assert response.ok is False
    assert response.error_code == "UNKNOWN_TRADEFLOW_OPERATION"
    assert inner.requests == []
    recorded = await observations.list_observations()
    assert len(recorded) == 1
    assert recorded[0].value == "loyalty.calculate_secret_score"
    assert recorded[0].source == "raw_adapter_request"


@pytest.mark.asyncio
async def test_tradeflow_write_requires_idempotency_key() -> None:
    from datetime import timedelta

    from ntheemba.adapters.tradeflow import IdempotentTradeFlowContractAdapter
    from ntheemba.infrastructure.memory import MemoryIdempotencyStore

    inner = InMemoryTradeFlowContractAdapter(
        business_id="serahs",
        handlers={TradeFlowOperation.APPOINTMENT_CREATE_REQUEST: _ok},
    )
    adapter = IdempotentTradeFlowContractAdapter(
        inner,
        MemoryIdempotencyStore(),
        ttl=timedelta(days=7),
    )

    response = await adapter.execute(
        TradeFlowRequest(
            request_id="request-write",
            business_id="serahs",
            operation=TradeFlowOperation.APPOINTMENT_CREATE_REQUEST,
        )
    )

    assert response.ok is False
    assert response.error_code == "IDEMPOTENCY_KEY_REQUIRED"
    assert inner.requests == []


@pytest.mark.asyncio
async def test_tradeflow_write_replays_completed_result_without_second_call() -> None:
    from datetime import timedelta

    from ntheemba.adapters.tradeflow import IdempotentTradeFlowContractAdapter
    from ntheemba.infrastructure.memory import MemoryIdempotencyStore

    calls = 0

    async def create(_request: TradeFlowRequest) -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"requestId": "BOOK-1"}

    inner = InMemoryTradeFlowContractAdapter(
        business_id="serahs",
        handlers={TradeFlowOperation.APPOINTMENT_CREATE_REQUEST: create},
    )
    adapter = IdempotentTradeFlowContractAdapter(
        inner,
        MemoryIdempotencyStore(),
        ttl=timedelta(days=7),
    )
    request = TradeFlowRequest(
        request_id="request-write-1",
        business_id="serahs",
        operation=TradeFlowOperation.APPOINTMENT_CREATE_REQUEST,
        idempotency_key="booking-customer-1",
    )

    first = await adapter.execute(request)
    replay = await adapter.execute(
        TradeFlowRequest(
            request_id="request-write-2",
            business_id="serahs",
            operation=TradeFlowOperation.APPOINTMENT_CREATE_REQUEST,
            idempotency_key="booking-customer-1",
        )
    )

    assert first.ok is True
    assert replay.ok is True
    assert replay.data["requestId"] == "BOOK-1"
    assert calls == 1
