"""Least-privilege, real-HTTP Ntheemba <-> NCPC synthetic proof."""

from __future__ import annotations

import asyncio
import json
import os
from decimal import Decimal
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import httpx
from ntheemba.adapters.ncpc import HttpNCPCAdapter, NCPCResponseError, NCPCUnavailableError
from ntheemba.adapters.tradeflow.http import HttpTradeFlowAdapter, TradeFlowResponseError
from ntheemba.domain.product_resolution import ProductQuery

NCPC_URL = os.environ.get("NCPC_PROOF_URL", "http://ncpc:8080").rstrip("/")
NCPC_TOKEN = os.environ["NTHEEMBA_NCPC_API_TOKEN"]
NAME, BARCODE = "Ntheemba NCPC HTTP Proof Product", "0088888888882"
FORBIDDEN = frozenset(
    {
        "price",
        "selling_price",
        "cost",
        "stock",
        "availability",
        "supplier",
        "batch",
        "order",
        "sale",
        "revenue",
        "margin",
    }
)


def _raw(
    method: str, path: str, body: dict[str, object] | None = None
) -> tuple[int, dict[str, object]]:
    request = Request(
        f"{NCPC_URL}{path}",
        method=method,
        data=json.dumps(body).encode() if body else None,
        headers={
            "Authorization": f"Bearer {NCPC_TOKEN}",
            "Content-Type": "application/json",
            "X-Request-ID": "nint-reader",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def _identity_only(value: object) -> None:
    if isinstance(value, dict):
        assert not any(key.casefold() in FORBIDDEN for key in value), value
        for child in value.values():
            _identity_only(child)
    elif isinstance(value, list):
        for child in value:
            _identity_only(child)


async def run() -> None:
    status, raw = _raw("GET", "/v1/catalogue/candidates?query=nint%20proof%20alias")
    assert status == 200 and raw.get("success") is True, raw
    _identity_only(raw)
    candidates = raw["data"]["candidates"]
    assert isinstance(candidates, list) and len(candidates) == 1
    product_id, variant_id = candidates[0]["ncpc_product_id"], candidates[0]["ncpc_variant_id"]
    assert (product_id, variant_id) == ("PRD-000001", "VAR-000001")
    ncpc = HttpNCPCAdapter(
        base_url=NCPC_URL, bearer_token=NCPC_TOKEN, allow_local_http_hosts=frozenset({"ncpc"})
    )
    found = await ncpc.search_products(ProductQuery("nint proof alias"))
    assert (
        len(found) == 1
        and found[0].product_id == product_id
        and await ncpc.resolve_barcode(BARCODE) == found[0]
    )
    assert not hasattr(found[0], "selling_price") and not hasattr(found[0], "stock")
    status, denied = _raw(
        "POST",
        "/v1/submissions/products",
        {
            "business_id": "nint-proof-business",
            "business_product_ref": "NINT-READ-DENY",
            "idempotency_key": "nint-reader-denied-001",
            "canonical_name": "Nint reader denied",
            "source": "synthetic_nint_proof",
        },
    )
    assert status == 403 and denied.get("error", {}).get("code") == "FORBIDDEN", denied
    status, denied = _raw("GET", "/v1/admin/publications")
    assert status == 403 and denied.get("error", {}).get("code") == "FORBIDDEN", denied
    a = HttpTradeFlowAdapter(
        business_id="nint-a",
        base_url="https://tradeflow-a:8443/exec",
        api_token="local-proof-tradeflow-token",
        verify_tls=False,
        allow_private_destination_hosts=frozenset({"tradeflow-a"}),
    )
    b = HttpTradeFlowAdapter(
        business_id="nint-b",
        base_url="https://tradeflow-b:8443/exec",
        api_token="local-proof-tradeflow-token",
        verify_tls=False,
        allow_private_destination_hosts=frozenset({"tradeflow-b"}),
    )
    products_a, products_b = (
        await a.filter_business_products("nint-a", (variant_id,)),
        await b.filter_business_products("nint-b", (variant_id,)),
    )
    assert len(products_a) == len(products_b) == 1
    assert products_a[0].selling_price == Decimal("12.50") and products_a[0].available is True
    assert products_b[0].selling_price == Decimal("19.75") and products_b[0].available is False
    try:
        await a.filter_business_products("nint-b", (variant_id,))
    except TradeFlowResponseError as error:
        assert error.code == "TENANT_MISMATCH"
    else:
        raise AssertionError("cross-business adapter request was not rejected")
    async with httpx.AsyncClient(verify=False, timeout=5) as client:
        wrong = await client.post(
            "https://tradeflow-b:8443/exec",
            json={
                "api_token": "local-proof-tradeflow-token",
                "business_id": "nint-a",
                "action": "catalogue.by_ncpc_variant",
                "data": {"ncpc_variant_id": variant_id},
            },
        )
    assert wrong.status_code == 403 and wrong.json()["error"]["code"] == "TENANT_MISMATCH"
    bad = HttpNCPCAdapter(
        base_url=NCPC_URL,
        bearer_token="invalid-local-proof-token",
        allow_local_http_hosts=frozenset({"ncpc"}),
    )
    try:
        await bad.search_products(ProductQuery(NAME))
    except NCPCResponseError as error:
        assert error.code == "UNAUTHORIZED"
    else:
        raise AssertionError("invalid NCPC token was accepted")
    unavailable = HttpNCPCAdapter(
        base_url="http://ncpc:65530",
        bearer_token=NCPC_TOKEN,
        timeout_seconds=0.5,
        allow_local_http_hosts=frozenset({"ncpc"}),
    )
    try:
        await unavailable.search_products(ProductQuery(NAME))
    except NCPCUnavailableError:
        pass
    else:
        raise AssertionError("NCPC network outage was not classified safely")
    print("NTHEEMBA_NCPC_REAL_HTTP_SYNTHETIC_PROOF_PASSED")


if __name__ == "__main__":
    asyncio.run(run())
