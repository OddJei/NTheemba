from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from ntheemba.adapters.businesses import InMemoryBusinessRegistry
from ntheemba.adapters.marketplace import InMemoryMarketplaceRegistry
from ntheemba.adapters.secrets import StaticSecretResolver
from ntheemba.adapters.tradeflow.factory import HttpTradeFlowPortFactory
from ntheemba.adapters.tradeflow.runtime_port import DynamicTradeFlowPort
from ntheemba.application.business_workflow_runtime import BusinessWorkflowRuntime
from ntheemba.application.capability_runtime import CapabilityAwareWorkflowRouter
from ntheemba.application.marketplace import (
    MarketplaceHandoffConsumptionService,
    MarketplaceOrderBridgeService,
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
from ntheemba.domain.marketplace import (
    MarketplaceBusinessListing,
    MarketplaceHandoff,
    MarketplaceListingStatus,
)
from ntheemba.services.product_resolver import ProductResolver
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.catalogue import CatalogueWorkflow
from ntheemba.workflows.order import OrderWorkflow, build_order_routes
from tests.fakes.ncpc import InMemoryNCPC


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
        frozenset(
            {
                Capability.PRODUCT_CATALOGUE.value,
                Capability.PRODUCT_ORDER.value,
                Capability.COLLECTION.value,
            }
        ),
        runtime_revision=4,
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
            {
                Capability.PRODUCT_CATALOGUE.value,
                Capability.PRODUCT_ORDER.value,
            }
        ),
    )


def _item() -> dict[str, object]:
    return {
        "business_product_id": "A1",
        "business_id": "BUS-A",
        "shop_id": "shop-a",
        "identity": {
            "status": "linked",
            "ncpc_prd_id": "PRD-1",
            "ncpc_var_id": "VAR-1",
        },
        "identity_status": "linked",
        "name": "Blue Band 500g",
        "selling_price": "25.00",
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


@pytest.mark.asyncio
async def test_marketplace_order_bridge_mutates_only_selected_business_http_endpoint() -> None:
    calls: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        body = json.loads(request.content.decode("utf-8"))
        action = str(body.get("action") or "")
        token = str(body.get("api_token") or "")
        calls.append((host, action, token))
        if host == "bus-b.test":
            raise AssertionError("BUS-B must never be called for a BUS-A handoff/order")
        assert host == "bus-a.test"
        assert token == "token-a"
        if action == "catalogue.item":
            return httpx.Response(200, json={"ok": True, "data": {"item": _item()}})
        if action == "order.create":
            data = body.get("data") or {}
            assert data.get("shop_id") == "shop-a"
            assert data.get("idempotency_key") == "MPORDER:MPH-A"
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "data": {
                        "order": {"order_id": "ORD-A-1", "status": "requested"},
                        "duplicate": False,
                    },
                },
            )
        raise AssertionError(f"unexpected action {action}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        a = _business("BUS-A")
        b = _business("BUS-B")
        ia = _integration("BUS-A", "bus-a.test", "env:A")
        ib = _integration("BUS-B", "bus-b.test", "env:B")
        businesses = InMemoryBusinessRegistry(
            businesses=(a, b),
            integrations=(ia, ib),
        )
        marketplace = InMemoryMarketplaceRegistry(
            listings=(
                MarketplaceBusinessListing("BUS-A", MarketplaceListingStatus.ACTIVE, True),
                MarketplaceBusinessListing("BUS-B", MarketplaceListingStatus.ACTIVE, True),
            ),
            handoffs=(
                MarketplaceHandoff(
                    handoff_id="MPH-A",
                    search_id="MPS-A",
                    result_id="MPS-A:1",
                    source_channel_id="platform-marketplace",
                    target_business_id="BUS-A",
                    business_product_id="A1",
                    ncpc_product_id="PRD-1",
                    ncpc_variant_id="VAR-1",
                    product_name="Blue Band 500g",
                    selling_price_snapshot=Decimal("25.00"),
                    currency="ZMW",
                    integration_id="TF-BUS-A",
                    business_runtime_revision=4,
                    shop_id="shop-a",
                    created_at=datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
                ),
            ),
        )
        factory = HttpTradeFlowPortFactory(
            secrets=StaticSecretResolver({"env:A": "token-a", "env:B": "token-b"}),
            client=client,
        )
        consumed = await MarketplaceHandoffConsumptionService(
            businesses=businesses,
            marketplace=marketplace,
            tradeflow_factory=factory,
        ).consume(_platform(), "MPH-A")

        dynamic = DynamicTradeFlowPort(factory=factory)
        responses = ResponseBuilder()
        catalogue = CatalogueWorkflow(
            resolver=ProductResolver(ncpc=InMemoryNCPC(()), tradeflow=dynamic),
            tradeflow=dynamic,
            responses=responses,
        )
        order = OrderWorkflow(catalogue=catalogue, tradeflow=dynamic, responses=responses)
        runtime = BusinessWorkflowRuntime(
            CapabilityAwareWorkflowRouter(WorkflowRouter(build_order_routes(order)))
        )
        bridge = MarketplaceOrderBridgeService(runtime=runtime)
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
                customer_name="James Chisulo",
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

    assert "ORD-A-1" in (result.replies[0].text or "")
    assert result.replies[0].metadata["created"] is True
    assert ("bus-a.test", "order.create", "token-a") in calls
    assert all(host != "bus-b.test" for host, _action, _token in calls)
