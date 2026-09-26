"""Deterministic gateway -> NCPC -> exact-tenant TradeFlow integration proof."""

from __future__ import annotations

import json
from collections import Counter
from types import MappingProxyType

import httpx
import pytest

from ntheemba.adapters.businesses import InMemoryBusinessRegistry
from ntheemba.adapters.ncpc.http import HttpNCPCAdapter
from ntheemba.adapters.secrets import StaticSecretResolver
from ntheemba.adapters.tradeflow.factory import HttpTradeFlowPortFactory
from ntheemba.application.composition import build_deterministic_runtime
from ntheemba.config import Settings
from ntheemba.domain.business import BusinessChannel, BusinessIntegration, BusinessProfile
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.gateway import InboundGatewayMessage
from ntheemba.infrastructure.storage import StorageRuntime
from ntheemba.ports.sessions import SessionKey
from tests.fakes.audit import InMemoryAuditSink
from tests.fakes.publisher import InMemoryOutgoingPublisher


BUS_A = "BUS-A"
BUS_B = "BUS-B"
CAPS = frozenset({Capability.PRODUCT_CATALOGUE.value})


def _business(business_id: str) -> BusinessProfile:
    return BusinessProfile(
        business_id=business_id,
        display_name=f"{business_id} Shop",
        adapter_type="tradeflow_standard",
        declared_capabilities=CAPS,
        runtime_revision=1,
    )


def _channel(business_id: str, suffix: str) -> BusinessChannel:
    return BusinessChannel(
        channel_instance_id=f"wa-{suffix}",
        provider="openwa",
        business_id=business_id,
        phone_e164=f"+2609700000{suffix}",
    )


def _integration(business_id: str, host: str, token_ref: str) -> BusinessIntegration:
    return BusinessIntegration(
        integration_id=f"tf-{business_id.lower()}",
        business_id=business_id,
        adapter_type="tradeflow_standard",
        provider="tradeflow_http",
        base_url=f"https://{host}/exec",
        auth_reference=token_ref,
        capabilities=CAPS,
        config=MappingProxyType({"timeout_seconds": 1.0}),
    )


def _ncpc_response(candidates: list[dict[str, object]]) -> httpx.Response:
    return httpx.Response(
        200,
        json={"success": True, "data": {"candidates": candidates}},
    )


def _tf_response(data: dict[str, object]) -> httpx.Response:
    return httpx.Response(200, json={"ok": True, "data": data})


def _canonical_blue_band() -> dict[str, object]:
    return {
        "ncpc_product_id": "PRD-BLUE-BAND",
        "ncpc_variant_id": "VAR-BLUE-BAND-500G",
        "canonical_name": "Blue Band Margarine 500 g",
        "brand": "Blue Band",
        "variant_name": "500 g tub",
        "pack_definition": {"primary_measure": {"value": "500", "unit": "g"}},
        "identifiers": ["6001000000001"],
        "aliases": ["Blueband", "Blue Band 500g"],
        "catalogue_version": "ncpc-test-v1",
    }


def _business_product(
    *,
    business_id: str,
    product_id: str,
    name: str,
    price: str,
    identity_status: str,
    ncpc_prd_id: str | None = None,
    ncpc_var_id: str | None = None,
    shop_id: str = "main",
) -> dict[str, object]:
    identity: dict[str, object] = {"status": identity_status}
    if ncpc_prd_id:
        identity["ncpc_prd_id"] = ncpc_prd_id
    if ncpc_var_id:
        identity["ncpc_var_id"] = ncpc_var_id
    return {
        "business_product_id": product_id,
        "business_id": business_id,
        "shop_id": shop_id,
        "name": name,
        "selling_price": price,
        "currency": "ZMW",
        "availability": {"status": "in_stock"},
        "identity_status": identity_status,
        "identity": identity,
    }


class RoutedMockBackend:
    """One transport that records every public dependency host/action call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.tf_tokens: list[tuple[str, str]] = []

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        if host == "ncpc.test":
            self.calls.append((host, request.url.path))
            query = request.url.params.get("query", "").casefold()
            barcode = request.url.params.get("barcode", "")
            if barcode == "6001000000001" or "blue band" in query:
                return _ncpc_response([_canonical_blue_band()])
            return _ncpc_response([])

        body = json.loads(request.content.decode("utf-8"))
        action = str(body.get("action") or "")
        self.calls.append((host, action))
        self.tf_tokens.append((host, str(body.get("api_token") or "")))
        business_id = str(body.get("business_id") or "")
        data = body.get("data") if isinstance(body.get("data"), dict) else {}

        if host == "bus-a.test":
            assert business_id == BUS_A
            if action == "catalogue.by_ncpc_variant":
                assert data.get("ncpc_variant_id") == "VAR-BLUE-BAND-500G"
                return _tf_response(
                    {
                        "items": [
                            _business_product(
                                business_id=BUS_A,
                                product_id="A-BLUE-500",
                                name="Blue Band 500g",
                                price="42.50",
                                identity_status="linked",
                                ncpc_prd_id="PRD-BLUE-BAND",
                                ncpc_var_id="VAR-BLUE-BAND-500G",
                            )
                        ]
                    }
                )
            if action == "catalogue.item":
                product_id = str(data.get("business_product_id") or "")
                if product_id == "A-BLUE-500":
                    return _tf_response(
                        {
                            "item": _business_product(
                                business_id=BUS_A,
                                product_id="A-BLUE-500",
                                name="Blue Band 500g",
                                price="42.50",
                                identity_status="linked",
                                ncpc_prd_id="PRD-BLUE-BAND",
                                ncpc_var_id="VAR-BLUE-BAND-500G",
                            )
                        }
                    )
                if product_id == "A-LOCAL-RELISH":
                    return _tf_response(
                        {
                            "item": _business_product(
                                business_id=BUS_A,
                                product_id="A-LOCAL-RELISH",
                                name="Local Relish Mix",
                                price="18.00",
                                identity_status="awaiting_ncpc_review",
                            )
                        }
                    )
            if action == "catalogue.search":
                query = str(data.get("query") or "").casefold()
                if "local relish" in query:
                    return _tf_response(
                        {
                            "items": [
                                _business_product(
                                    business_id=BUS_A,
                                    product_id="A-LOCAL-RELISH",
                                    name="Local Relish Mix",
                                    price="18.00",
                                    identity_status="awaiting_ncpc_review",
                                )
                            ]
                        }
                    )
                if "secret local" in query:
                    return _tf_response(
                        {
                            "items": [
                                _business_product(
                                    business_id=BUS_A,
                                    product_id="A-LOCAL-HIDDEN",
                                    name="Secret Local Product",
                                    price="9.00",
                                    identity_status="local_only",
                                )
                            ]
                        }
                    )
                return _tf_response({"items": []})

        if host == "bus-b.test":
            # BUS-B deliberately has a conflicting copy. BUS-A requests must never touch it.
            assert business_id == BUS_B
            if action == "catalogue.by_ncpc_variant":
                return _tf_response(
                    {
                        "items": [
                            _business_product(
                                business_id=BUS_B,
                                product_id="B-BLUE-500",
                                name="Blue Band 500g - B",
                                price="99.99",
                                identity_status="linked",
                                ncpc_prd_id="PRD-BLUE-BAND",
                                ncpc_var_id="VAR-BLUE-BAND-500G",
                            )
                        ]
                    }
                )
            if action == "catalogue.search":
                return _tf_response(
                    {
                        "items": [
                            _business_product(
                                business_id=BUS_B,
                                product_id="B-LOCAL-RELISH",
                                name="BUS B Local Relish",
                                price="77.00",
                                identity_status="awaiting_ncpc_review",
                            )
                        ]
                    }
                )
            if action == "catalogue.item":
                return _tf_response({"item": None})

        return httpx.Response(404, json={"ok": False, "error": {"code": "NOT_FOUND"}})


@pytest.fixture
async def composed_runtime():
    backend = RoutedMockBackend()
    client = httpx.AsyncClient(transport=httpx.MockTransport(backend))
    settings = Settings(environment="test", dev_tools_enabled=False)
    storage = StorageRuntime(settings)
    businesses = (_business(BUS_A), _business(BUS_B))
    channels = (_channel(BUS_A, "1"), _channel(BUS_B, "2"))
    integrations = (
        _integration(BUS_A, "bus-a.test", "env:BUS_A_TOKEN"),
        _integration(BUS_B, "bus-b.test", "env:BUS_B_TOKEN"),
    )
    storage.business_registry = InMemoryBusinessRegistry(
        businesses=businesses,
        channels=channels,
        integrations=integrations,
    )
    publisher = InMemoryOutgoingPublisher()
    audit = InMemoryAuditSink()
    runtime = build_deterministic_runtime(
        storage=storage,
        ncpc=HttpNCPCAdapter(
            base_url="https://ncpc.test",
            bearer_token="ncpc-token",
            client=client,
        ),
        tradeflow_factory=HttpTradeFlowPortFactory(
            secrets=StaticSecretResolver(
                {
                    "env:BUS_A_TOKEN": "token-a",
                    "env:BUS_B_TOKEN": "token-b",
                }
            ),
            client=client,
        ),
        audit=audit,
        publisher=publisher,
    )
    try:
        yield runtime, backend, publisher, audit
    finally:
        await client.aclose()


def _message(*, message_id: str, text: str) -> InboundGatewayMessage:
    return InboundGatewayMessage(
        request_id=f"REQ-{message_id}",
        message_id=message_id,
        channel_instance_id="wa-1",
        provider="openwa",
        recipient_phone="+26097000001",
        customer_phone="+260955000001",
        text=text,
    )


@pytest.mark.asyncio
async def test_gateway_ncpc_tradeflow_path_uses_only_exact_tenant(composed_runtime) -> None:
    runtime, backend, publisher, audit = composed_runtime

    first = await runtime.gateway.process(
        _message(message_id="BLUE-1", text="Do you have Blue Band 500g?")
    )
    second = await runtime.gateway.process(_message(message_id="BLUE-2", text="yes"))

    assert first.business.business.business_id == BUS_A
    assert second.business.business.business_id == BUS_A
    assert publisher.messages
    all_text = " ".join(message.text or "" for message in publisher.messages)
    assert "42.50" in all_text
    assert "99.99" not in all_text
    assert "B-BLUE-500" not in all_text

    hosts = Counter(host for host, _action in backend.calls)
    assert hosts["ncpc.test"] >= 1
    assert hosts["bus-a.test"] >= 2
    assert hosts["bus-b.test"] == 0
    assert all(token == "token-a" for host, token in backend.tf_tokens if host == "bus-a.test")
    assert any(event.business_id == BUS_A for event in audit.events)


@pytest.mark.asyncio
async def test_ncpc_miss_falls_back_to_same_tenant_pending_review_without_fake_ids(
    composed_runtime,
) -> None:
    runtime, backend, publisher, _audit = composed_runtime

    await runtime.gateway.process(
        _message(message_id="LOCAL-1", text="Do you have local relish?")
    )
    await runtime.gateway.process(_message(message_id="LOCAL-2", text="yes"))

    all_text = " ".join(message.text or "" for message in publisher.messages)
    assert "Local Relish Mix" in all_text
    assert "18.00" in all_text
    assert "PRD-" not in all_text
    assert "VAR-" not in all_text
    assert "BUS B Local Relish" not in all_text
    assert all(host != "bus-b.test" for host, _action in backend.calls)

    # The selected session result itself must remain provisional and identity-null.
    customer = await runtime.gateway.customers.resolve_platform_customer("+260955000001")
    session = await runtime.core.coordinator.repository.load(SessionKey(BUS_A, customer.customer_id))
    assert session is not None
    assert session.product_resolution is not None
    selected = session.product_resolution.selected
    assert selected is not None
    assert selected.business_product_id == "A-LOCAL-RELISH"
    assert selected.identity_status == "awaiting_ncpc_review"
    assert selected.trusted_identity is False
    assert selected.ncpc_product_id is None
    assert selected.ncpc_variant_id is None


@pytest.mark.asyncio
async def test_local_only_tradeflow_product_remains_hidden_from_ntheemba(composed_runtime) -> None:
    runtime, backend, publisher, _audit = composed_runtime

    await runtime.gateway.process(
        _message(message_id="HIDDEN-1", text="Do you have secret local product?")
    )

    all_text = " ".join(message.text or "" for message in publisher.messages)
    assert "Secret Local Product" not in all_text
    assert all(host != "bus-b.test" for host, _action in backend.calls)
