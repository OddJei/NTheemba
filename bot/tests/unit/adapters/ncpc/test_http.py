from __future__ import annotations

import httpx
import pytest
from ntheemba.adapters.ncpc import HttpNCPCAdapter, NCPCResponseError, NCPCUnavailableError
from ntheemba.domain.product_resolution import ProductQuery


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_candidate_search_maps_identity_only_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer ncpc-test-token"
        assert request.url.params["query"] == "Blue Band 500ml"
        return httpx.Response(
            200,
            json={
                "version": "v1",
                "request_id": "r1",
                "success": True,
                "error": None,
                "data": {
                    "candidates": [
                        {
                            "ncpc_product_id": "PRD-BLUE-BAND",
                            "ncpc_variant_id": "VAR-BLUE-BAND-500ML",
                            "canonical_name": "Blue Band",
                            "variant_name": "Original",
                            "brand": "Blue Band",
                            "category": "Spreads",
                            "pack_definition": {"primary_measure": {"value": 500, "unit": "ml"}},
                            "attributes": {"selling_price": 999, "stock": 42},
                            "identifiers": ["6001234567890"],
                            "aliases": ["blueband"],
                            "catalogue_version": "abc123",
                            "release_version": "2026.09",
                            "match_type": "token",
                        }
                    ]
                },
            },
        )

    async with _client(handler) as client:
        adapter = HttpNCPCAdapter(
            base_url="https://ncpc.test",
            bearer_token="ncpc-test-token",
            client=client,
        )
        products = await adapter.search_products(ProductQuery("Blue Band 500ml"))

    assert len(products) == 1
    product = products[0]
    assert product.product_id == "PRD-BLUE-BAND"
    assert product.variant_id == "VAR-BLUE-BAND-500ML"
    assert str(product.size_value) == "500"
    assert product.size_unit == "ml"
    assert product.barcode == "6001234567890"
    assert not hasattr(product, "selling_price")


@pytest.mark.asyncio
async def test_candidate_search_skips_product_family_rows_without_variant_identity() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "version": "v1",
                "request_id": "r-family",
                "success": True,
                "error": None,
                "data": {
                    "candidates": [
                        {
                            "ncpc_product_id": "PRD-FAMILY",
                            "ncpc_variant_id": "",
                            "canonical_name": "Family Only",
                        },
                        {
                            "ncpc_product_id": "PRD-ANJOY",
                            "ncpc_variant_id": "VAR-ANJOY-1",
                            "canonical_name": "Anjoy Flavoured Drink",
                            "pack_definition": {},
                            "identifiers": [],
                            "aliases": [],
                        },
                    ]
                },
            },
        )

    async with _client(handler) as client:
        adapter = HttpNCPCAdapter(
            base_url="https://ncpc.test",
            bearer_token="token",
            client=client,
        )
        products = await adapter.search_products(ProductQuery("I want to order Anjoy"))

    assert [product.variant_id for product in products] == ["VAR-ANJOY-1"]


@pytest.mark.asyncio
async def test_barcode_no_match_returns_none() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "version": "v1",
                "request_id": "r2",
                "success": True,
                "error": None,
                "data": {"candidates": []},
            },
        )

    async with _client(handler) as client:
        adapter = HttpNCPCAdapter(
            base_url="https://ncpc.test", bearer_token="token", client=client
        )
        assert await adapter.resolve_barcode("6000000000000") is None


@pytest.mark.asyncio
async def test_auth_failure_is_safe_response_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "version": "v1",
                "request_id": "r3",
                "success": False,
                "data": None,
                "error": {"code": "AUTHENTICATION_FAILED", "message": "invalid credentials"},
            },
    )

    async with _client(handler) as client:
        adapter = HttpNCPCAdapter(
            base_url="https://ncpc.test",
            bearer_token="secret-value",
            client=client,
        )
        with pytest.raises(NCPCResponseError, match="rejected") as caught:
            await adapter.search_products(ProductQuery("Sugar"))

    assert "secret-value" not in str(caught.value)


@pytest.mark.asyncio
async def test_transport_failure_becomes_unavailable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    async with _client(handler) as client:
        adapter = HttpNCPCAdapter(base_url="https://ncpc.test", bearer_token="token", client=client)
        with pytest.raises(NCPCUnavailableError, match="temporarily unavailable"):
            await adapter.search_products(ProductQuery("Sugar"))

@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/v1",
        "https://127.0.0.1/v1",
        "https://10.0.0.4/v1",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/v1",
    ],
)
def test_ncpc_adapter_rejects_literal_non_public_destination(url: str) -> None:
    with pytest.raises(ValueError, match=r"localhost|non-public IP"):
        HttpNCPCAdapter(base_url=url, bearer_token="token")


def test_ncpc_adapter_allows_only_explicit_development_compose_address() -> None:
    adapter = HttpNCPCAdapter(
        base_url="http://ncpc:8080",
        bearer_token="token",
        allow_development_internal_ncpc=True,
    )

    assert adapter.base_url == "http://ncpc:8080"
    with pytest.raises(ValueError, match="absolute HTTPS endpoint"):
        HttpNCPCAdapter(
            base_url="http://another-service:8080",
            bearer_token="token",
            allow_development_internal_ncpc=True,
        )
