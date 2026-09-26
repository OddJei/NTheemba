from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ntheemba.adapters.businesses import InMemoryBusinessRegistry
from ntheemba.adapters.marketplace import InMemoryMarketplaceRegistry
from ntheemba.application.gateway_worker import WorkerAction
from ntheemba.application.inbound_runtime import build_inbound_processing_runtime
from ntheemba.config import Settings
from ntheemba.domain.business import (
    BusinessChannel,
    BusinessIntegration,
    BusinessProfile,
    ChannelRole,
    ChannelScope,
)
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.gateway import InboundGatewayMessage
from ntheemba.domain.marketplace import MarketplaceBusinessListing, MarketplaceListingStatus
from ntheemba.domain.platform_session import PlatformConversationStage
from ntheemba.infrastructure.storage import StorageRuntime
from ntheemba.ports.ncpc import CanonicalProduct
from ntheemba.ports.platform_sessions import PlatformSessionKey
from ntheemba.ports.tradeflow import BusinessProduct
from tests.fakes.ncpc import InMemoryNCPC
from tests.fakes.tradeflow import InMemoryTradeFlow


class StaticFactory:
    def __init__(self, port: InMemoryTradeFlow) -> None:
        self.port = port

    def build(self, _integration):
        return self.port


def _message(message_id: str, text: str) -> InboundGatewayMessage:
    return InboundGatewayMessage(
        request_id=f"REQ-{message_id}",
        message_id=message_id,
        channel_instance_id="platform-marketplace",
        provider="waha",
        recipient_phone="+260970000099",
        customer_phone="+260970000001",
        text=text,
        received_at=datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_generic_inbound_worker_routes_platform_marketplace_to_business_order_state() -> None:
    storage = StorageRuntime(Settings(environment="test", dev_tools_enabled=False))
    business = BusinessProfile(
        "BUS-A",
        "Business A",
        "tradeflow_standard",
        frozenset(
            {
                Capability.PRODUCT_CATALOGUE.value,
                Capability.PRODUCT_ORDER.value,
            }
        ),
        runtime_revision=2,
    )
    integration = BusinessIntegration(
        "TF-A",
        "BUS-A",
        "tradeflow_standard",
        "https://a.example/exec",
        capabilities=frozenset(
            {
                Capability.PRODUCT_CATALOGUE.value,
                Capability.PRODUCT_ORDER.value,
            }
        ),
    )
    platform = BusinessChannel(
        "platform-marketplace",
        "waha",
        None,
        "+260970000099",
        scope=ChannelScope.PLATFORM,
        role=ChannelRole.MARKETPLACE,
        external_session_id="platform-marketplace",
        recipient_identifier="+260970000099",
    )
    storage.business_registry = InMemoryBusinessRegistry(
        businesses=(business,),
        channels=(platform,),
        integrations=(integration,),
    )
    storage.marketplace_registry = InMemoryMarketplaceRegistry(
        listings=(
            MarketplaceBusinessListing(
                "BUS-A",
                MarketplaceListingStatus.ACTIVE,
                True,
            ),
        )
    )
    tradeflow = InMemoryTradeFlow()
    tradeflow.products["BUS-A"] = {
        "A1": BusinessProduct(
            "A1",
            "PRD-1",
            "Blue Band 500g",
            Decimal("25"),
            "ZMW",
            5,
            ncpc_variant_id="VAR-1",
            shop_id="SHOP-A",
        )
    }
    runtime = build_inbound_processing_runtime(
        storage=storage,
        ncpc=InMemoryNCPC(
            (CanonicalProduct("PRD-1", "Blue Band 500g", variant_id="VAR-1"),)
        ),
        tradeflow_factory=StaticFactory(tradeflow),  # type: ignore[arg-type]
        audit=storage.audit_sink,
        consumer_id="worker-1",
        max_attempts=3,
    )

    for message_id, text in (
        ("MSG-1", "Blue Band 500g"),
        ("MSG-2", "1"),
        ("MSG-3", "continue"),
    ):
        await storage.gateway_queue.enqueue_inbound(_message(message_id, text))
        result = await runtime.worker.run_once()
        assert result.action is WorkerAction.ACKNOWLEDGED

    platform_customer = await storage.customer_directory.resolve_by_phone("+260970000001")
    platform_session = await storage.platform_session_repository.load(
        PlatformSessionKey("platform-marketplace", platform_customer.customer_id)
    )
    assert platform_session is not None
    assert platform_session.stage is PlatformConversationStage.BUSINESS_ACTIVE
    assert platform_session.target_business_id == "BUS-A"
    assert platform_session.business_conversation_id

    # Platform replies never fake tenant channel ownership.
    outbound = []
    while True:
        claimed = await storage.gateway_queue.claim_outbound("sender")
        if claimed is None:
            break
        outbound.append(claimed.message)
        await storage.gateway_queue.acknowledge_outbound(claimed.delivery_id, "sender")
    assert outbound
    assert all(item.scope is ChannelScope.PLATFORM for item in outbound)
    assert all(item.business_id == "" for item in outbound)
    assert all(item.channel_instance_id == "platform-marketplace" for item in outbound)
    assert all(item.platform_role is ChannelRole.MARKETPLACE for item in outbound)

    # N14 bridge entered the selected business's normal order flow but did not submit yet.
    assert all(call[0] != "create_order_request" for call in tradeflow.calls)
