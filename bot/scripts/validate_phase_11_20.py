"""Run a synthetic Phase 11.20 contract-freeze acceptance check."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from dataclasses import asdict, dataclass

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ntheemba.adapters.businesses import InMemoryUnsupportedDeclarationSink
from ntheemba.adapters.tradeflow import (
    CapabilityControlledTradeFlowAdapter,
    InMemoryTradeFlowContractAdapter,
    NtheembaTradeFlowIngress,
)
from ntheemba.config import Settings
from ntheemba.domain.business import (
    BusinessChannel,
    BusinessProfile,
    ResolvedBusinessContext,
)
from ntheemba.domain.capabilities import Capability
from ntheemba.main import create_app


@dataclass(frozen=True, slots=True)
class ValidationResult:
    status: str
    checks: tuple[str, ...]


def _send(
    client: TestClient,
    conversation_id: str,
    text: str,
    index: int,
) -> dict[str, object]:
    response = client.post(
        "/dev/simulator/workspace/messages",
        json={
            "conversation_id": conversation_id,
            "text": text,
            "message_id": f"phase-11-20-{conversation_id}-{index}",
            "request_id": f"phase-11-20-request-{conversation_id}-{index}",
        },
    )
    response.raise_for_status()
    return response.json()


async def _unknown_method_check() -> None:
    business = BusinessProfile(
        "validation-business",
        "Validation Business",
        "tradeflow_standard",
        frozenset({Capability.PRODUCT_CATALOGUE.value}),
    )
    channel = BusinessChannel(
        "validation-channel",
        "validation-provider",
        business.business_id,
        "+260970009999",
    )
    context = ResolvedBusinessContext(
        business,
        channel,
        frozenset({Capability.PRODUCT_CATALOGUE}),
    )
    observations = InMemoryUnsupportedDeclarationSink()
    inner = InMemoryTradeFlowContractAdapter(
        business_id=business.business_id,
        handlers={},
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
        request_id="unknown-method-check",
        business_id=business.business_id,
        operation="tradeflow.enable_itself",
    )
    assert response.error_code == "UNKNOWN_TRADEFLOW_OPERATION"
    assert not inner.requests
    recorded = await observations.list_observations()
    assert len(recorded) == 1
    assert recorded[0].value == "tradeflow.enable_itself"


def main() -> int:
    checks: list[str] = []
    app = create_app(Settings(environment="test", docs_enabled=False))
    with TestClient(app) as client:
        businesses = client.get("/dev/simulator/workspace/businesses")
        businesses.raise_for_status()
        payload = businesses.json()
        assert [item["business_id"] for item in payload] == [
            "harvest-big-shop",
            "amac-enterprise",
            "serahs-glow-lounge",
        ]
        assert "loyalty.read" in payload[-1]["capabilities"]
        checks.append("canonical business capability profiles")

        denied = _send(
            client,
            "conv-amac-delivery-denied",
            "Order cooking oil for delivery",
            1,
        )
        assert "not enabled" in denied["replies"][0]["text"]
        assert denied["session"]["flow"] == "idle"
        checks.append("disabled capability denied before workflow execution")

        loyalty = _send(
            client,
            "conv-serah-natasha",
            "How many loyalty points do I have?",
            1,
        )
        assert "Silver" in loyalty["replies"][0]["text"]
        checks.append("Serah client recognition and TradeFlow-owned loyalty result")

        conversations = client.get("/dev/simulator/workspace/conversations").json()
        chanda = next(
            item for item in conversations if item["conversation_id"] == "conv-serah-chanda"
        )
        latest: dict[str, object] = {}
        for index, text in enumerate(chanda["suggested_messages"], start=1):
            latest = _send(client, chanda["conversation_id"], text, index)
        assert latest["session"]["stage"] == "submitted"
        assert latest["session"]["selected_service"] == "Knotless Braids"
        assert latest["session"]["submitted_request_id"]
        checks.append("new Serah client and appointment submission")

        harvest_scenario = next(
            item
            for item in conversations
            if item["conversation_id"] == "conv-harvest-ruth"
        )
        harvest_ruth: dict[str, object] = {}
        for index, text in enumerate(harvest_scenario["suggested_messages"], start=1):
            harvest_ruth = _send(
                client,
                harvest_scenario["conversation_id"],
                text,
                index,
            )
        assert harvest_ruth["session"]["stage"] == "submitted"
        assert harvest_ruth["session"]["submitted_request_id"]
        checks.append("complete Standard TradeFlow delivery order")

        serah_ruth = _send(
            client,
            "conv-serah-ruth",
            "How many loyalty points do I have?",
            1,
        )
        assert (
            harvest_ruth["session"]["customer_id"]
            == serah_ruth["session"]["customer_id"]
        )
        assert (
            harvest_ruth["session"]["conversation_id"]
            != serah_ruth["session"]["conversation_id"]
        )
        assert (
            harvest_ruth["session"]["business_id"]
            != serah_ruth["session"]["business_id"]
        )
        checks.append("shared platform customer with isolated business sessions")

        trace = client.get(
            "/dev/simulator/requests/phase-11-20-request-conv-serah-natasha-1/trace"
        )
        trace.raise_for_status()
        nodes = {event["node_id"] for event in trace.json()}
        assert {
            "gateway.message",
            "business.resolve",
            "capabilities.load",
            "customer.resolve",
            "capabilities.validate",
        } <= nodes
        checks.append("business and capability pipeline tracing")

    asyncio.run(_unknown_method_check())
    checks.append("unknown TradeFlow method rejected and observed")

    result = ValidationResult("passed", tuple(checks))
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
