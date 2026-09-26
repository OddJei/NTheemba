from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ntheemba.adapters.businesses import InMemoryBusinessRegistry
from ntheemba.adapters.marketplace import InMemoryMarketplaceRegistry
from ntheemba.adapters.tradeflow.runtime_port import DynamicTradeFlowPort
from ntheemba.application.business_workflow_runtime import BusinessWorkflowRuntime
from ntheemba.application.capability_runtime import CapabilityAwareWorkflowRouter
from ntheemba.application.marketplace import (
    MarketplaceHandoffConsumptionService,
    MarketplaceOrderBridgeService,
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
    ResolvedBusinessContext,
    ResolvedPlatformContext,
)
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.enums import FulfilmentMethod, IntentType, MessageRole, Stage
from ntheemba.domain.intents import EntitySet, Intent
from ntheemba.domain.marketplace import (
    MarketplaceBusinessHandoffContext,
    MarketplaceBusinessListing,
    MarketplaceHandoff,
    MarketplaceHandoffStatus,
    MarketplaceListingStatus,
)
from ntheemba.ports.tradeflow import BusinessProduct
from ntheemba.services.product_resolver import ProductResolver
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.catalogue import CatalogueWorkflow
from ntheemba.workflows.order import OrderWorkflow, build_order_routes
from tests.fakes.audit import InMemoryAuditSink
from tests.fakes.ncpc import InMemoryNCPC
from tests.fakes.tradeflow import InMemoryTradeFlow


class _StaticFactory:
    def __init__(self, port: InMemoryTradeFlow) -> None:
        self.port = port

    def build(self, integration: BusinessIntegration) -> InMemoryTradeFlow:
        assert integration.business_id == "BUS-A"
        return self.port


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


def _business() -> BusinessProfile:
    return BusinessProfile(
        "BUS-A",
        "Business A",
        "fake",
        frozenset(
            {
                Capability.PRODUCT_CATALOGUE.value,
                Capability.PRODUCT_ORDER.value,
                Capability.COLLECTION.value,
            }
        ),
        runtime_revision=7,
    )


def _integration() -> BusinessIntegration:
    return BusinessIntegration(
        "TF-BUS-A",
        "BUS-A",
        "fake",
        "https://bus-a.test/exec",
        provider="tradeflow_http",
        capabilities=frozenset(
            {
                Capability.PRODUCT_CATALOGUE.value,
                Capability.PRODUCT_ORDER.value,
            }
        ),
    )


def _handoff() -> MarketplaceHandoff:
    return MarketplaceHandoff(
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
        business_runtime_revision=7,
        shop_id="shop-a",
        created_at=datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
    )


def _tradeflow() -> InMemoryTradeFlow:
    port = InMemoryTradeFlow()
    port.products["BUS-A"] = {
        "A1": BusinessProduct(
            business_product_id="A1",
            ncpc_product_id="PRD-1",
            ncpc_variant_id="VAR-1",
            name="Blue Band 500g",
            selling_price=Decimal("25.00"),
            currency="ZMW",
            available_quantity=8,
            shop_id="shop-a",
            identity_status="linked",
        )
    }
    return port


def _setup():
    business = _business()
    integration = _integration()
    businesses = InMemoryBusinessRegistry(
        businesses=(business,),
        integrations=(integration,),
    )
    marketplace = InMemoryMarketplaceRegistry(
        listings=(
            MarketplaceBusinessListing(
                "BUS-A",
                MarketplaceListingStatus.ACTIVE,
                True,
            ),
        ),
        handoffs=(_handoff(),),
    )
    port = _tradeflow()
    audit = InMemoryAuditSink()
    consumption = MarketplaceHandoffConsumptionService(
        businesses=businesses,
        marketplace=marketplace,
        tradeflow_factory=_StaticFactory(port),
        audit=audit,
    )
    return business, integration, businesses, marketplace, port, audit, consumption


@pytest.mark.asyncio
async def test_ready_handoff_consumes_after_business_product_shop_and_price_revalidation() -> None:
    _business_obj, _integration_obj, _businesses, marketplace, port, audit, consumption = _setup()
    context = await consumption.consume(
        _platform(),
        "MPH-A",
        now=datetime(2026, 9, 4, 12, 5, tzinfo=UTC),
    )

    assert context.handoff.status is MarketplaceHandoffStatus.CONSUMED
    assert context.handoff.consumed_at == datetime(2026, 9, 4, 12, 5, tzinfo=UTC)
    assert await marketplace.get_handoff("MPH-A") == context.handoff
    assert ("get_business_product", ("BUS-A", "A1")) in port.calls
    assert (
        "check_product_availability",
        ("BUS-A", "A1", 1, "shop-a"),
    ) in port.calls
    assert [event.event_type for event in audit.events] == ["marketplace.handoff_consumed"]


@pytest.mark.asyncio
async def test_consumption_is_idempotent_after_listing_is_paused() -> None:
    _business_obj, _integration_obj, _businesses, marketplace, _port, audit, consumption = _setup()
    platform = _platform()
    first = await consumption.consume(platform, "MPH-A")
    await marketplace.save_listing(
        MarketplaceBusinessListing("BUS-A", MarketplaceListingStatus.PAUSED, False)
    )
    second = await consumption.consume(platform, "MPH-A")

    assert second.handoff == first.handoff
    assert len(audit.events) == 1


@pytest.mark.asyncio
async def test_consumption_fails_closed_when_business_revision_changed() -> None:
    business, _integration_obj, businesses, marketplace, port, _audit, _consumption = _setup()
    await businesses.register_business(
        BusinessProfile(
            business.business_id,
            business.display_name,
            business.adapter_type,
            business.declared_capabilities,
            runtime_revision=8,
        )
    )
    consumption = MarketplaceHandoffConsumptionService(
        businesses=businesses,
        marketplace=marketplace,
        tradeflow_factory=_StaticFactory(port),
    )

    with pytest.raises(MarketplaceSelectionError, match="configuration changed"):
        await consumption.consume(_platform(), "MPH-A")


def _runtime(port: InMemoryTradeFlow) -> BusinessWorkflowRuntime:
    dynamic = DynamicTradeFlowPort({"fake": port})
    responses = ResponseBuilder()
    catalogue = CatalogueWorkflow(
        resolver=ProductResolver(ncpc=InMemoryNCPC(()), tradeflow=dynamic),
        tradeflow=dynamic,
        responses=responses,
    )
    order = OrderWorkflow(
        catalogue=catalogue,
        tradeflow=dynamic,
        responses=responses,
    )
    router = CapabilityAwareWorkflowRouter(WorkflowRouter(build_order_routes(order)))
    return BusinessWorkflowRuntime(router)


def _intent(intent_type: IntentType, **entities) -> Intent:
    return Intent(
        type=intent_type,
        role=MessageRole.PENDING_ANSWER,
        confidence=1.0,
        entities=EntitySet(raw_text=intent_type.value, **entities),
    )


@pytest.mark.asyncio
async def test_consumed_handoff_enters_existing_order_workflow_and_submits_idempotently() -> None:
    _business_obj, _integration_obj, _businesses, _marketplace, port, _audit, consumption = _setup()
    consumed = await consumption.consume(_platform(), "MPH-A")
    bridge = MarketplaceOrderBridgeService(runtime=_runtime(port))

    started = await bridge.start_order(
        consumed,
        customer_id="CUSTOMER-1",
        request_id="REQ-START",
        message_id="MSG-START",
    )
    session = started.session
    assert session.stage is Stage.QUANTITY
    assert session.order_draft is not None
    assert session.order_draft.idempotency_key == "MPORDER:MPH-A"
    assert session.order_draft.product is not None
    assert session.order_draft.product.shop_id == "shop-a"

    await bridge.continue_order(
        consumed,
        session,
        _intent(IntentType.PROVIDE_QUANTITY, quantity=2),
        request_id="REQ-QTY",
        message_id="MSG-QTY",
    )
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
    first = await bridge.continue_order(
        consumed,
        session,
        _intent(IntentType.CONFIRM),
        request_id="REQ-CONFIRM",
        message_id="MSG-CONFIRM",
    )
    second = await bridge.continue_order(
        consumed,
        session,
        _intent(IntentType.CONFIRM),
        request_id="REQ-CONFIRM-RETRY",
        message_id="MSG-CONFIRM",
    )

    assert len(port.orders) == 1
    assert "MPORDER:MPH-A" in port.orders
    create_calls = [call for call in port.calls if call[0] == "create_order_request"]
    assert len(create_calls) == 1
    submitted_request = create_calls[0][1][1]
    assert submitted_request.business_product_id == "A1"
    assert submitted_request.shop_id == "shop-a"
    assert first.replies[0].metadata["created"] is True
    assert second.replies[0].metadata["created"] is False


@pytest.mark.asyncio
async def test_ready_handoff_cannot_enter_order_bridge() -> None:
    business, integration, _businesses, _marketplace, port, _audit, _consumption = _setup()
    context = MarketplaceBusinessHandoffContext(
        source_platform_context=_platform(),
        business=business,
        capabilities=frozenset(
            {
                Capability.PRODUCT_CATALOGUE,
                Capability.PRODUCT_ORDER,
                Capability.COLLECTION,
            }
        ),
        integrations=(integration,),
        handoff=_handoff(),
    )
    bridge = MarketplaceOrderBridgeService(runtime=_runtime(port))

    with pytest.raises(MarketplaceSelectionError, match="consumed handoff"):
        await bridge.start_order(
            context,
            customer_id="CUSTOMER-1",
            request_id="REQ",
            message_id="MSG",
        )


@pytest.mark.asyncio
async def test_unified_runtime_executes_normal_business_and_marketplace_contexts() -> None:
    business, integration, _businesses, _marketplace, port, _audit, consumption = _setup()
    runtime = _runtime(port)
    consumed = await consumption.consume(_platform(), "MPH-A")
    normal = ResolvedBusinessContext(
        business=business,
        channel=BusinessChannel("business-a", "waha", "BUS-A", "+260970000001"),
        capabilities=frozenset(
            {
                Capability.PRODUCT_CATALOGUE,
                Capability.PRODUCT_ORDER,
                Capability.COLLECTION,
            }
        ),
        integrations=(integration,),
    )

    def selected_session(conversation_id: str):
        from ntheemba.domain.enums import Flow
        from ntheemba.domain.product_resolution import ProductQuery, ProductResolution, ResolvedProduct
        from ntheemba.domain.session import Session
        from ntheemba.domain.transitions import TransitionPolicy

        session = Session.create("BUS-A", "CUSTOMER-1", conversation_id=conversation_id)
        policy = TransitionPolicy()
        session.transition_to(policy, Flow.CATALOGUE, Stage.CATALOGUE_SEARCH)
        session.transition_to(policy, Flow.CATALOGUE, Stage.PRODUCT_SELECTED)
        session.product_resolution = ProductResolution.resolved(
            ProductQuery("Blue Band 500g"),
            ResolvedProduct(
                ncpc_product_id="PRD-1",
                ncpc_variant_id="VAR-1",
                business_product_id="A1",
                business_id="BUS-A",
                name="Blue Band 500g",
                selling_price=Decimal("25.00"),
                currency="ZMW",
                available=True,
                shop_id="shop-a",
            ),
            confidence=1.0,
        )
        return session

    normal_session = selected_session("NORMAL-1")
    market_session = selected_session("MARKET-1")
    normal_result = await runtime.route(
        execution_context=normal,
        session=normal_session,
        intent=_intent(IntentType.START_ORDER),
        request_id="REQ-NORMAL",
        message_id="MSG-NORMAL",
    )
    market_result = await runtime.route(
        execution_context=consumed,
        session=market_session,
        intent=_intent(IntentType.START_ORDER),
        request_id="REQ-MARKET",
        message_id="MSG-MARKET",
    )

    assert normal_session.stage is Stage.QUANTITY
    assert market_session.stage is Stage.QUANTITY
    assert normal_result.replies[0].metadata == market_result.replies[0].metadata
