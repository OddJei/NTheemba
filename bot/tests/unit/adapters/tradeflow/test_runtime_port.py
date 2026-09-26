from __future__ import annotations

from datetime import date

import pytest
from ntheemba.adapters.tradeflow import (
    DynamicTradeFlowPort,
    RuntimeIntegrationUnavailableError,
)
from ntheemba.application.runtime_context import bind_runtime_context
from ntheemba.domain.business import (
    BusinessChannel,
    BusinessIntegration,
    BusinessProfile,
    ResolvedBusinessContext,
)
from ntheemba.domain.capabilities import Capability
from tests.fakes.tradeflow import InMemoryTradeFlow


def _context(
    *,
    business_id: str,
    adapter_type: str,
    capabilities: frozenset[Capability],
    integrations: tuple[BusinessIntegration, ...],
) -> ResolvedBusinessContext:
    return ResolvedBusinessContext(
        business=BusinessProfile(
            business_id,
            business_id.title(),
            adapter_type,
            frozenset(capability.value for capability in capabilities),
            runtime_revision=1,
        ),
        channel=BusinessChannel(
            f"wa-{business_id}",
            "openwa",
            business_id,
            "+260970000001",
        ),
        capabilities=capabilities,
        integrations=integrations,
        runtime_revision=1,
    )


@pytest.mark.asyncio
async def test_harvest_booking_denied_without_underlying_tradeflow_call() -> None:
    harvest = InMemoryTradeFlow()
    port = DynamicTradeFlowPort({"tradeflow_standard": harvest})
    context = _context(
        business_id="harvest",
        adapter_type="tradeflow_standard",
        capabilities=frozenset(
            {Capability.PRODUCT_CATALOGUE, Capability.PRODUCT_ORDER}
        ),
        integrations=(
            BusinessIntegration(
                "harvest-tradeflow",
                "harvest",
                "tradeflow_standard",
                "https://tradeflow.local/harvest",
                capabilities=frozenset(
                    {
                        Capability.PRODUCT_CATALOGUE.value,
                        Capability.PRODUCT_ORDER.value,
                    }
                ),
            ),
        ),
    )

    with bind_runtime_context(context):
        with pytest.raises(RuntimeIntegrationUnavailableError):
            await port.get_available_slots(
                "harvest",
                "svc-1",
                appointment_date=date(2026, 8, 22),
            )

    assert harvest.calls == []


@pytest.mark.asyncio
async def test_serah_booking_uses_serah_configured_integration_only() -> None:
    standard = InMemoryTradeFlow()
    serah = InMemoryTradeFlow()
    serah.slots[("serah", "svc-1", date(2026, 8, 22))] = ()
    port = DynamicTradeFlowPort(
        {
            "tradeflow_standard": standard,
            "tradeflow_serahs": serah,
        }
    )
    context = _context(
        business_id="serah",
        adapter_type="tradeflow_serahs",
        capabilities=frozenset(
            {Capability.SERVICE_CATALOGUE, Capability.APPOINTMENT_CREATE}
        ),
        integrations=(
            BusinessIntegration(
                "serah-tradeflow",
                "serah",
                "tradeflow_serahs",
                "https://tradeflow.local/serah",
                capabilities=frozenset(
                    {
                        Capability.SERVICE_CATALOGUE.value,
                        Capability.APPOINTMENT_CREATE.value,
                    }
                ),
            ),
        ),
    )

    with bind_runtime_context(context):
        await port.get_available_slots(
            "serah",
            "svc-1",
            appointment_date=date(2026, 8, 22),
        )

    assert standard.calls == []
    assert serah.calls == [
        ("get_available_slots", ("serah", "svc-1", date(2026, 8, 22)))
    ]
