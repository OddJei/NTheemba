"""Two-business deterministic staging proof without transport or LLM dependencies."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from ntheemba.adapters.businesses import InMemoryBusinessRegistry
from ntheemba.adapters.marketplace import InMemoryMarketplaceRegistry
from ntheemba.adapters.ncpc.http import HttpNCPCAdapter
from ntheemba.adapters.secrets import StaticSecretResolver
from ntheemba.adapters.tradeflow.factory import HttpTradeFlowPortFactory
from ntheemba.adapters.tradeflow.runtime_port import DynamicTradeFlowPort
from ntheemba.application.business_workflow_runtime import BusinessWorkflowRuntime
from ntheemba.application.capability_runtime import CapabilityAwareWorkflowRouter
from ntheemba.application.marketplace import (
    MarketplaceHandoffConsumptionService,
    MarketplaceHandoffService,
    MarketplaceOrderBridgeService,
    MarketplaceProductDiscoveryService,
    MarketplaceSelectionError,
)
from ntheemba.application.workflow_router import WorkflowRouter
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
from ntheemba.domain.enums import FulfilmentMethod, IntentType, MessageRole
from ntheemba.domain.intents import EntitySet, Intent
from ntheemba.domain.marketplace import MarketplaceBusinessListing, MarketplaceListingStatus
from ntheemba.domain.product_resolution import ProductQuery
from ntheemba.services.product_resolver import ProductResolver
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.catalogue import CatalogueWorkflow
from ntheemba.workflows.order import OrderWorkflow, build_order_routes
from tests.fakes.ncpc import InMemoryNCPC


CAPS = frozenset(
    {
        Capability.PRODUCT_CATALOGUE.value,
        Capability.PRODUCT_ORDER.value,
        Capability.COLLECTION.value,
    }
)


def _business(business_id: str, *, revision: int = 1) -> BusinessProfile:
    return BusinessProfile(
        business_id,
        f"{business_id} Shop",
        "tradeflow_standard",
        CAPS,
        runtime_revision=revision,
    )


def _integration(business_id: str, host: str, ref: str) -> BusinessIntegration:
    return BusinessIntegration(
        f"TF-{business_id}",
        business_id,
        "tradeflow_standard",
        f"https://{host}/exec",
        provider="tradeflow_http",
        auth_reference=ref,
        capabilities=frozenset(
            {Capability.PRODUCT_CATALOGUE.value, Capability.PRODUCT_ORDER.value}
        ),
    )


def _platform(channel_id: str = "platform-marketplace") -> ResolvedPlatformContext:
    channel = BusinessChannel(
        channel_id,
        "waha",
        None,
        "+260970000099",
        scope=ChannelScope.PLATFORM,
        role=ChannelRole.MARKETPLACE,
        external_session_id=channel_id,
    )
    return ResolvedPlatformContext(
        channel,
        ChannelRole.MARKETPLACE,
        frozenset({PlatformCapability.MARKETPLACE}),
    )


def _item(business_id: str, product_id: str, price: str) -> dict[str, object]:
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


def _intent(intent_type: IntentType, **entities) -> Intent:
    return Intent(
        type=intent_type,
        role=MessageRole.PENDING_ANSWER,
        confidence=1.0,
        entities=EntitySet(raw_text=intent_type.value, **entities),
    )


class TwoBusinessBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.order_ids: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
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
                                "catalogue_version": "stage-v1",
                            }
                        ]
                    },
                },
            )
        body = json.loads(request.content.decode("utf-8"))
        action = str(body.get("action") or "")
        token = str(body.get("api_token") or "")
        business_id = str(body.get("business_id") or "")
        self.calls.append((host, action, token))
        if host == "bus-a.test":
            assert business_id == "BUS-A"
            assert token == "token-a"
            item = _item("BUS-A", "A1", "30.00")
        elif host == "bus-b.test":
            assert business_id == "BUS-B"
            assert token == "token-b"
            item = _item("BUS-B", "B1", "28.00")
        else:
            raise AssertionError(f"unexpected tenant host {host}")

        if action == "catalogue.by_ncpc_variant":
            return httpx.Response(200, json={"ok": True, "data": {"items": [item]}})
        if action == "catalogue.item":
            return httpx.Response(200, json={"ok": True, "data": {"item": item}})
        if action == "order.create":
            data = body.get("data") if isinstance(body.get("data"), dict) else {}
            assert business_id == "BUS-A"
            assert data.get("shop_id") == "shop-bus-a"
            assert str(data.get("idempotency_key", "")).startswith("MPORDER:")
            order_id = "ORD-A-1"
            self.order_ids.append(order_id)
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "data": {
                        "order": {"order_id": order_id, "status": "requested"},
                        "duplicate": False,
                    },
                },
            )
        raise AssertionError(f"unexpected action {action}")


@pytest.mark.asyncio
async def test_two_business_marketplace_to_selected_business_order_is_tenant_safe() -> None:
    backend = TwoBusinessBackend()
    transport = httpx.MockTransport(backend)
    async with httpx.AsyncClient(transport=transport) as client:
        a, b, c = _business("BUS-A"), _business("BUS-B"), _business("BUS-C")
        ia = _integration("BUS-A", "bus-a.test", "env:A")
        ib = _integration("BUS-B", "bus-b.test", "env:B")
        ic = _integration("BUS-C", "bus-c.test", "env:C")
        businesses = InMemoryBusinessRegistry(
            businesses=(a, b, c), integrations=(ia, ib, ic)
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
        platform = _platform()
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
        handoffs = MarketplaceHandoffService(
            businesses=businesses,
            marketplace=marketplace,
            tradeflow_factory=factory,
        )
        consumption = MarketplaceHandoffConsumptionService(
            businesses=businesses,
            marketplace=marketplace,
            tradeflow_factory=factory,
        )

        search = await discovery.search(platform, ProductQuery("Blue Band"))
        assert {offer.business_id for offer in search.offers} == {"BUS-A", "BUS-B"}
        selected = next(offer for offer in search.offers if offer.business_id == "BUS-A")
        selected_context = await handoffs.select(platform, search, selected.result_id)
        consumed = await consumption.consume(platform, selected_context.handoff.handoff_id)

        dynamic = DynamicTradeFlowPort(factory=factory)
        responses = ResponseBuilder()
        catalogue = CatalogueWorkflow(
            resolver=ProductResolver(ncpc=InMemoryNCPC(()), tradeflow=dynamic),
            tradeflow=dynamic,
            responses=responses,
        )
        order = OrderWorkflow(catalogue=catalogue, tradeflow=dynamic, responses=responses)
        bridge = MarketplaceOrderBridgeService(
            runtime=BusinessWorkflowRuntime(
                CapabilityAwareWorkflowRouter(WorkflowRouter(build_order_routes(order)))
            )
        )
        started = await bridge.start_order(
            consumed,
            customer_id="CUSTOMER-1",
            request_id="REQ-START",
            message_id="MSG-START",
            quantity=1,
        )
        session = started.session
        await bridge.continue_order(
            consumed,
            session,
            _intent(
                IntentType.PROVIDE_FULFILMENT_METHOD,
                fulfilment_method=FulfilmentMethod.COLLECTION,
            ),
            request_id="REQ-FULFIL",
            message_id="MSG-FULFIL",
        )
        await bridge.continue_order(
            consumed,
            session,
            _intent(
                IntentType.PROVIDE_CUSTOMER_DETAILS,
                customer_name="James",
                contact_number="0970000000",
            ),
            request_id="REQ-CUSTOMER",
            message_id="MSG-CUSTOMER",
        )
        result = await bridge.continue_order(
            consumed,
            session,
            _intent(IntentType.CONFIRM),
            request_id="REQ-CONFIRM",
            message_id="MSG-CONFIRM",
        )
        # A repeated confirmation after a successful submission cannot mutate again.
        await bridge.continue_order(
            consumed,
            session,
            _intent(IntentType.CONFIRM),
            request_id="REQ-CONFIRM-2",
            message_id="MSG-CONFIRM-2",
        )

    assert "ORD-A-1" in (result.replies[0].text or "")
    assert backend.order_ids == ["ORD-A-1"]
    assert any(host == "bus-a.test" and action == "order.create" for host, action, _ in backend.calls)
    assert not any(host == "bus-b.test" and action == "order.create" for host, action, _ in backend.calls)
    assert not any(host == "bus-c.test" for host, _action, _token in backend.calls)


@pytest.mark.asyncio
async def test_handoff_cannot_be_consumed_from_another_platform_channel() -> None:
    backend = TwoBusinessBackend()
    transport = httpx.MockTransport(backend)
    async with httpx.AsyncClient(transport=transport) as client:
        a = _business("BUS-A")
        ia = _integration("BUS-A", "bus-a.test", "env:A")
        businesses = InMemoryBusinessRegistry(businesses=(a,), integrations=(ia,))
        marketplace = InMemoryMarketplaceRegistry(
            listings=(
                MarketplaceBusinessListing("BUS-A", MarketplaceListingStatus.ACTIVE, True),
            )
        )
        factory = HttpTradeFlowPortFactory(
            secrets=StaticSecretResolver({"env:A": "token-a"}), client=client
        )
        discovery = MarketplaceProductDiscoveryService(
            businesses=businesses,
            marketplace=marketplace,
            ncpc=HttpNCPCAdapter(
                base_url="https://ncpc.test", bearer_token="ncpc-token", client=client
            ),
            tradeflow_factory=factory,
        )
        handoffs = MarketplaceHandoffService(
            businesses=businesses, marketplace=marketplace, tradeflow_factory=factory
        )
        consumption = MarketplaceHandoffConsumptionService(
            businesses=businesses, marketplace=marketplace, tradeflow_factory=factory
        )
        source = _platform("marketplace-source")
        search = await discovery.search(source, ProductQuery("Blue Band"))
        ready = await handoffs.select(source, search, search.offers[0].result_id)
        before = len(backend.calls)

        with pytest.raises(MarketplaceSelectionError, match="another platform channel"):
            await consumption.consume(_platform("marketplace-attacker"), ready.handoff.handoff_id)

    assert len(backend.calls) == before


@pytest.mark.asyncio
async def test_handoff_fails_closed_after_selected_business_revision_changes() -> None:
    backend = TwoBusinessBackend()
    transport = httpx.MockTransport(backend)
    async with httpx.AsyncClient(transport=transport) as client:
        a = _business("BUS-A", revision=1)
        ia = _integration("BUS-A", "bus-a.test", "env:A")
        businesses = InMemoryBusinessRegistry(businesses=(a,), integrations=(ia,))
        marketplace = InMemoryMarketplaceRegistry(
            listings=(
                MarketplaceBusinessListing("BUS-A", MarketplaceListingStatus.ACTIVE, True),
            )
        )
        factory = HttpTradeFlowPortFactory(
            secrets=StaticSecretResolver({"env:A": "token-a"}), client=client
        )
        platform = _platform()
        discovery = MarketplaceProductDiscoveryService(
            businesses=businesses,
            marketplace=marketplace,
            ncpc=HttpNCPCAdapter(
                base_url="https://ncpc.test", bearer_token="ncpc-token", client=client
            ),
            tradeflow_factory=factory,
        )
        handoffs = MarketplaceHandoffService(
            businesses=businesses, marketplace=marketplace, tradeflow_factory=factory
        )
        consumption = MarketplaceHandoffConsumptionService(
            businesses=businesses, marketplace=marketplace, tradeflow_factory=factory
        )
        search = await discovery.search(platform, ProductQuery("Blue Band"))
        ready = await handoffs.select(platform, search, search.offers[0].result_id)
        await businesses.register_business(_business("BUS-A", revision=2))
        before = len(backend.calls)

        with pytest.raises(MarketplaceSelectionError, match="configuration changed"):
            await consumption.consume(platform, ready.handoff.handoff_id)

    assert len(backend.calls) == before
