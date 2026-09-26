from __future__ import annotations

import base64
import hashlib
import hmac
import json

import httpx
import pytest

from ntheemba.adapters.secrets import StaticSecretResolver
from ntheemba.adapters.tradeflow import (
    DynamicTradeFlowPort,
    HttpTradeFlowAdapter,
    HttpTradeFlowPortFactory,
    TradeFlowResponseError,
)
from ntheemba.application.runtime_context import bind_runtime_context
from ntheemba.domain.business import BusinessChannel, BusinessIntegration, BusinessProfile, ResolvedBusinessContext
from ntheemba.domain.capabilities import Capability


def _product(product_id: str = "101", variant_id: str = "VAR-001") -> dict[str, object]:
    return {
        "business_product_id": product_id,
        "shop_id": "shop-main",
        "identity": {
            "status": "linked",
            "linked": True,
            "ncpc_prd_id": "PRD-001",
            "ncpc_var_id": variant_id,
        },
        "identity_status": "linked",
        "catalogue_source": "tradeflow_local_catalogue",
        "name": "Blue Band 500ml",
        "selling_price": 42.5,
        "currency": "ZMW",
        "availability": {"status": "in_stock"},
    }


@pytest.mark.asyncio
async def test_filter_products_calls_exact_tenant_endpoint_and_maps_business_facts() -> None:
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        assert body["business_id"] == "BUS_A"
        assert body["api_token"] == "tenant-a-secret"
        assert body["action"] == "catalogue.by_ncpc_variant"
        variant = body["data"]["ncpc_variant_id"]
        return httpx.Response(
            200,
            json={
                "ok": True,
                "version": "v1",
                "request_id": body["request_id"],
                "data": {"shop_id": "shop-main", "items": [_product(variant_id=variant)]},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = HttpTradeFlowAdapter(
            business_id="BUS_A",
            base_url="https://tradeflow-a.test/exec",
            api_token="tenant-a-secret",
            default_shop_id="shop-main",
            client=client,
        )
        products = await adapter.filter_business_products("BUS_A", ("VAR-001",))

    assert len(products) == 1
    assert products[0].business_product_id == "101"
    assert products[0].ncpc_product_id == "PRD-001"
    assert products[0].ncpc_variant_id == "VAR-001"
    assert str(products[0].selling_price) == "42.5"
    assert products[0].available is True
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_adapter_blocks_cross_tenant_call_before_network() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = HttpTradeFlowAdapter(
            business_id="BUS_A",
            base_url="https://tradeflow-a.test/exec",
            api_token="secret",
            client=client,
        )
        with pytest.raises(TradeFlowResponseError) as caught:
            await adapter.get_business_product("BUS_B", "101")

    assert caught.value.code == "TENANT_MISMATCH"
    assert calls == 0


@pytest.mark.asyncio
async def test_signed_request_matches_tradeflow_canonical_signature_contract() -> None:
    signing_secret = "s" * 32

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        canonical = json.dumps(body["data"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        material = "\n".join(
            [
                "v1",
                body["business_id"],
                body["request_id"],
                "",
                body["action"],
                str(body["request_timestamp"]),
                body["request_nonce"],
                digest,
            ]
        )
        expected = base64.b64encode(
            hmac.new(signing_secret.encode(), material.encode(), hashlib.sha256).digest()
        ).decode()
        assert hmac.compare_digest(body["request_signature"], expected)
        return httpx.Response(
            200,
            json={
                "ok": True,
                "version": "v1",
                "request_id": body["request_id"],
                "data": {"shop_id": "shop-main", "item": _product()},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = HttpTradeFlowAdapter(
            business_id="BUS_A",
            base_url="https://tradeflow-a.test/exec",
            api_token="secret",
            signing_secret=signing_secret,
            default_shop_id="shop-main",
            client=client,
        )
        product = await adapter.get_business_product("BUS_A", "101")

    assert product is not None


@pytest.mark.asyncio
async def test_dynamic_port_factory_uses_resolved_integration_secret_reference() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["api_token"] == "resolved-token-a"
        assert str(request.url) == "https://tradeflow-a.test/exec"
        return httpx.Response(
            200,
            json={
                "ok": True,
                "version": "v1",
                "request_id": body["request_id"],
                "data": {"shop_id": "shop-main", "items": [_product()]},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        integration = BusinessIntegration(
            integration_id="tf-a",
            business_id="BUS_A",
            adapter_type="tradeflow_standard",
            base_url="https://tradeflow-a.test/exec",
            auth_reference="env:BUS_A_TRADEFLOW_TOKEN",
            capabilities=frozenset({Capability.PRODUCT_CATALOGUE.value}),
            config={"default_shop_id": "shop-main"},
        )
        context = ResolvedBusinessContext(
            business=BusinessProfile(
                "BUS_A",
                "Business A",
                "tradeflow_standard",
                frozenset({Capability.PRODUCT_CATALOGUE.value}),
            ),
            channel=BusinessChannel("wa-a", "openwa", "BUS_A", "+260970000001"),
            capabilities=frozenset({Capability.PRODUCT_CATALOGUE}),
            integrations=(integration,),
        )
        dynamic = DynamicTradeFlowPort(
            factory=HttpTradeFlowPortFactory(
                secrets=StaticSecretResolver({"env:BUS_A_TRADEFLOW_TOKEN": "resolved-token-a"}),
                client=client,
            )
        )
        with bind_runtime_context(context):
            products = await dynamic.filter_business_products("BUS_A", ("VAR-001",))

    assert products[0].business_product_id == "101"


@pytest.mark.asyncio
async def test_read_transport_failure_retries_once_with_fresh_request() -> None:
    request_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        request_ids.append(body["request_id"])
        if len(request_ids) == 1:
            raise httpx.ConnectError("temporary", request=request)
        return httpx.Response(
            200,
            json={
                "ok": True,
                "version": "v1",
                "request_id": body["request_id"],
                "data": {"shop_id": "shop-main", "item": _product()},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = HttpTradeFlowAdapter(
            business_id="BUS_A",
            base_url="https://tradeflow-a.test/exec",
            api_token="secret",
            default_shop_id="shop-main",
            client=client,
        )
        product = await adapter.get_business_product("BUS_A", "101")

    assert product is not None
    assert len(request_ids) == 2
    assert request_ids[0] != request_ids[1]


@pytest.mark.asyncio
async def test_adapter_follows_apps_script_redirect_with_safe_get_semantics() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if len(methods) == 1:
            return httpx.Response(302, headers={"location": "https://redirected.test/result"})
        return httpx.Response(
            200,
            json={"ok": True, "version": "v1", "request_id": "r1", "data": {"ok": True}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = HttpTradeFlowAdapter(
            business_id="BUS_A",
            base_url="https://tradeflow-a.test/exec",
            api_token="tenant-a-secret",
            client=client,
        )
        result = await adapter._request("health", {})

    assert result == {"ok": True}
    assert methods == ["POST", "GET"]


@pytest.mark.asyncio
async def test_adapter_rejects_method_preserving_redirect_before_forwarding_token() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(307, headers={"location": "https://redirected.test/result"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = HttpTradeFlowAdapter(
            business_id="BUS_A",
            base_url="https://tradeflow-a.test/exec",
            api_token="tenant-a-secret",
            client=client,
        )
        with pytest.raises(TradeFlowResponseError, match="unsafe redirect") as caught:
            await adapter._request("health", {})

    assert caught.value.code == "UNSAFE_REDIRECT"
    assert calls == 1
