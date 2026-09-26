from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest

from ntheemba.adapters.businesses import InMemoryBusinessRegistry
from ntheemba.adapters.marketplace import InMemoryMarketplaceRegistry
from ntheemba.adapters.ncpc.http import HttpNCPCAdapter
from ntheemba.adapters.secrets import StaticSecretResolver
from ntheemba.adapters.tradeflow.factory import HttpTradeFlowPortFactory
from ntheemba.application.marketplace import (
    MarketplaceHandoffService,
    MarketplaceProductDiscoveryService,
)
from ntheemba.domain.business import (
    BusinessChannel,
    BusinessIntegration,
    BusinessProfile,
    ChannelRole,
    ChannelScope,
    PlatformCapability,
    ResolvedPlatformContext,
)
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.marketplace import MarketplaceBusinessListing, MarketplaceListingStatus
from ntheemba.domain.product_resolution import ProductQuery


def _platform() -> ResolvedPlatformContext:
    channel = BusinessChannel(
        "platform-marketplace",
        "waha",
        None,
        "+260970000099",
        scope=ChannelScope.PLATFORM,
        role=ChannelRole.MARKETPLACE,
    )
    return ResolvedPlatformContext(
        channel,
        ChannelRole.MARKETPLACE,
        frozenset({PlatformCapability.MARKETPLACE}),
    )


def _business(business_id: str) -> BusinessProfile:
    return BusinessProfile(
        business_id,
        f"{business_id} Shop",
        "tradeflow_standard",
        frozenset({Capability.PRODUCT_CATALOGUE.value}),
        runtime_revision=3,
    )


def _integration(business_id: str, host: str, ref: str) -> BusinessIntegration:
    return BusinessIntegration(
        f"TF-{business_id}",
        business_id,
        "tradeflow_standard",
        f"https://{host}/exec",
        provider="tradeflow_http",
        auth_reference=ref,
        capabilities=frozenset({Capability.PRODUCT_CATALOGUE.value}),
    )


def _tf_item(business_id: str, product_id: str, price: str) -> dict[str, object]:
    return {
        "business_product_id": product_id,
        "business_id": business_id,
        "shop_id": f"shop-{business_id.lower()}",
        "identity": {
            "status": "linked",
            "ncpc_prd_id": "PRD-1",
            "ncpc_var_id": "VAR-1",
        },
        "identity_status": "linked",
        "name": "Blue Band 500g",
        "selling_price": price,
        "currency": "ZMW",
        "availability": {"status": "in_stock"},
    }


@pytest.mark.asyncio
async def test_http_marketplace_selection_revalidates_only_selected_business_endpoint() -> None:
    calls: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        if host == "ncpc.test":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "candidates": [
                            {
                                "ncpc_product_id": "PRD-1",
                                "ncpc_variant_id": "VAR-1",
                                "canonical_name": "Blue Band 500g",
                                "catalogue_version": "test-v1",
                            }
                        ]
                    },
                },
            )
        body = json.loads(request.content.decode("utf-8"))
        action = str(body.get("action") or "")
        token = str(body.get("api_token") or "")
        business_id = str(body.get("business_id") or "")
        calls.append((host, action, token))
        if host == "bus-a.test":
            assert business_id == "BUS-A"
            assert token == "token-a"
            price = "25.00" if action == "catalogue.by_ncpc_variant" else "26.00"
            item = _tf_item("BUS-A", "A1", price)
        elif host == "bus-b.test":
            assert business_id == "BUS-B"
            assert token == "token-b"
            item = _tf_item("BUS-B", "B1", "24.00")
        else:
            raise AssertionError(f"unexpected host {host}")
        data = {"items": [item]} if action == "catalogue.by_ncpc_variant" else {"item": item}
        return httpx.Response(200, json={"ok": True, "data": data})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        a, b, c = _business("BUS-A"), _business("BUS-B"), _business("BUS-C")
        ia = _integration("BUS-A", "bus-a.test", "env:A")
        ib = _integration("BUS-B", "bus-b.test", "env:B")
        ic = _integration("BUS-C", "bus-c.test", "env:C")
        businesses = InMemoryBusinessRegistry(
            businesses=(a, b, c),
            integrations=(ia, ib, ic),
        )
        marketplace = InMemoryMarketplaceRegistry(
            listings=(
                MarketplaceBusinessListing("BUS-A", MarketplaceListingStatus.ACTIVE, True),
                MarketplaceBusinessListing("BUS-B", MarketplaceListingStatus.ACTIVE, True),
                MarketplaceBusinessListing("BUS-C", MarketplaceListingStatus.PAUSED, False),
            )
        )
        factory = HttpTradeFlowPortFactory(
            secrets=StaticSecretResolver(
                {"env:A": "token-a", "env:B": "token-b", "env:C": "token-c"}
            ),
            client=client,
        )
        discovery = MarketplaceProductDiscoveryService(
            businesses=businesses,
            marketplace=marketplace,
            ncpc=HttpNCPCAdapter(
                base_url="https://ncpc.test",
                bearer_token="ncpc-token",
                client=client,
            ),
            tradeflow_factory=factory,
        )
        handoff = MarketplaceHandoffService(
            businesses=businesses,
            marketplace=marketplace,
            tradeflow_factory=factory,
        )
        platform = _platform()
        search = await discovery.search(platform, ProductQuery("Blue Band"))
        selected = next(offer for offer in search.offers if offer.business_id == "BUS-A")
        context = await handoff.select(platform, search, selected.result_id)

    assert context.handoff.target_business_id == "BUS-A"
    assert context.handoff.selling_price_snapshot == Decimal("26.00")
    assert ("bus-a.test", "catalogue.item", "token-a") in calls
    assert ("bus-b.test", "catalogue.item", "token-b") not in calls
    assert all(host != "bus-c.test" for host, _action, _token in calls)
