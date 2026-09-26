from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ntheemba.adapters.businesses import InMemoryBusinessRegistry
from ntheemba.adapters.marketplace import InMemoryMarketplaceRegistry
from ntheemba.application.gateway_worker import WorkerAction
from ntheemba.application.inbound_runtime import build_inbound_processing_runtime
from ntheemba.application.platform_session_coordinator import PlatformSessionCoordinator
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
from ntheemba.domain.platform_session import PlatformConversationSession, PlatformConversationStage
from ntheemba.domain.product_resolution import ProductQuery
from ntheemba.infrastructure.memory.platform_sessions import (
    MemoryPlatformSessionLockManager,
    MemoryPlatformSessionRepository,
)
from ntheemba.infrastructure.serialization import decode_platform_session, encode_platform_session
from ntheemba.infrastructure.storage import StorageRuntime
from ntheemba.ports.marketplace import MutableMarketplaceRegistry
from ntheemba.ports.ncpc import CanonicalProduct
from ntheemba.ports.platform_sessions import PlatformSessionKey
from ntheemba.ports.sessions import SessionKey
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
        received_at=datetime(2026, 9, 4, 15, 0, tzinfo=UTC),
    )


def _runtime():
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
    )
    storage.business_registry = InMemoryBusinessRegistry(
        businesses=(business,),
        channels=(platform,),
        integrations=(integration,),
    )
    marketplace: MutableMarketplaceRegistry = InMemoryMarketplaceRegistry(
        listings=(
            MarketplaceBusinessListing(
                "BUS-A",
                MarketplaceListingStatus.ACTIVE,
                True,
            ),
        )
    )
    storage.marketplace_registry = marketplace
    port = InMemoryTradeFlow()
    port.products["BUS-A"] = {
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
        tradeflow_factory=StaticFactory(port),  # type: ignore[arg-type]
        audit=storage.audit_sink,
        consumer_id="worker-1",
        max_attempts=3,
    )
    return storage, port, runtime


@pytest.mark.asyncio
async def test_platform_session_state_isolated_by_channel_and_customer() -> None:
    repo = MemoryPlatformSessionRepository()
    first = PlatformConversationSession.create("PLAT-A", "CUST-1")
    second = PlatformConversationSession.create("PLAT-A", "CUST-2")
    third = PlatformConversationSession.create("PLAT-B", "CUST-1")
    await repo.save(first, expected_revision=None)
    await repo.save(second, expected_revision=None)
    await repo.save(third, expected_revision=None)

    loaded = await repo.load(PlatformSessionKey("PLAT-A", "CUST-1"))

    assert loaded is not None
    assert loaded.conversation_id == first.conversation_id
    assert loaded.conversation_id != second.conversation_id
    assert loaded.conversation_id != third.conversation_id


def test_platform_session_serialization_round_trip_preserves_marketplace_state() -> None:
    session = PlatformConversationSession.create("PLAT-A", "CUST-1")
    # A no-result search is still durable platform state and carries its exact query.
    from ntheemba.domain.marketplace import MarketplaceProductSearch

    session.set_search(
        MarketplaceProductSearch(
            source_channel_id="PLAT-A",
            query=ProductQuery("Blue Band"),
        )
    )

    decoded = decode_platform_session(encode_platform_session(session))

    assert decoded.channel_instance_id == "PLAT-A"
    assert decoded.customer_id == "CUST-1"
    assert decoded.search is not None
    assert decoded.search.query.original_text == "Blue Band"
    assert decoded.stage is PlatformConversationStage.IDLE


@pytest.mark.asyncio
async def test_expired_platform_session_is_archived_and_replaced() -> None:
    repo = MemoryPlatformSessionRepository()
    locks = MemoryPlatformSessionLockManager()
    now = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
    clock_value = [now]
    coordinator = PlatformSessionCoordinator(
        repo,
        locks,
        clock=lambda: clock_value[0],
        ttl=timedelta(minutes=5),
    )
    async with coordinator.open("PLAT-A", "CUST-1") as managed:
        first_id = managed.session.conversation_id
        await managed.commit()
    clock_value[0] = now + timedelta(minutes=6)

    async with coordinator.open("PLAT-A", "CUST-1") as managed:
        second_id = managed.session.conversation_id

    assert second_id != first_id


@pytest.mark.asyncio
async def test_missing_business_session_steps_platform_back_to_safe_handoff_boundary() -> None:
    storage, _port, runtime = _runtime()
    for message_id, text in (
        ("MSG-1", "Blue Band 500g"),
        ("MSG-2", "1"),
        ("MSG-3", "continue"),
    ):
        await storage.gateway_queue.enqueue_inbound(_message(message_id, text))
        assert (await runtime.worker.run_once()).action is WorkerAction.ACKNOWLEDGED

    customer = await storage.customer_directory.resolve_by_phone("+260970000001")
    platform_key = PlatformSessionKey("platform-marketplace", customer.customer_id)
    platform_session = await storage.platform_session_repository.load(platform_key)
    assert platform_session is not None
    assert platform_session.stage is PlatformConversationStage.BUSINESS_ACTIVE
    await storage.session_repository.delete(SessionKey("BUS-A", customer.customer_id))

    await storage.gateway_queue.enqueue_inbound(_message("MSG-4", "2"))
    assert (await runtime.worker.run_once()).action is WorkerAction.ACKNOWLEDGED

    recovered = await storage.platform_session_repository.load(platform_key)
    assert recovered is not None
    assert recovered.stage is PlatformConversationStage.HANDOFF_READY
    assert recovered.handoff_id == platform_session.handoff_id
    assert recovered.business_conversation_id == ""

    await storage.gateway_queue.enqueue_inbound(_message("MSG-5", "continue"))
    assert (await runtime.worker.run_once()).action is WorkerAction.ACKNOWLEDGED
    reentered = await storage.platform_session_repository.load(platform_key)
    assert reentered is not None
    assert reentered.stage is PlatformConversationStage.BUSINESS_ACTIVE
    assert reentered.business_conversation_id
    assert reentered.business_conversation_id != platform_session.business_conversation_id


@pytest.mark.asyncio
async def test_stale_business_runtime_revision_resets_platform_marketplace_state() -> None:
    storage, _port, runtime = _runtime()
    for message_id, text in (
        ("MSG-1", "Blue Band 500g"),
        ("MSG-2", "1"),
        ("MSG-3", "continue"),
    ):
        await storage.gateway_queue.enqueue_inbound(_message(message_id, text))
        assert (await runtime.worker.run_once()).action is WorkerAction.ACKNOWLEDGED

    customer = await storage.customer_directory.resolve_by_phone("+260970000001")
    existing = await storage.business_registry.get_business("BUS-A")
    assert existing is not None
    await storage.business_registry.register_business(
        BusinessProfile(
            existing.business_id,
            existing.display_name,
            existing.adapter_type,
            existing.declared_capabilities,
            runtime_revision=existing.runtime_revision + 1,
        )
    )  # type: ignore[attr-defined]

    await storage.gateway_queue.enqueue_inbound(_message("MSG-4", "2"))
    assert (await runtime.worker.run_once()).action is WorkerAction.ACKNOWLEDGED

    platform_session = await storage.platform_session_repository.load(
        PlatformSessionKey("platform-marketplace", customer.customer_id)
    )
    assert platform_session is not None
    assert platform_session.stage is PlatformConversationStage.IDLE
    assert platform_session.target_business_id == ""
