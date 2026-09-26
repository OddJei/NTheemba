"""Redis Streams gateway queue contract tests."""

from datetime import UTC, datetime

import pytest

from ntheemba.domain.business import ChannelRole, ChannelScope
from ntheemba.domain.gateway import InboundGatewayMessage, OutboundGatewayMessage
from ntheemba.infrastructure.redis.gateway import RedisReliableGatewayQueue
from ntheemba.infrastructure.redis.keys import RedisKeyspace
from tests.fakes.redis_runtime import FakeRedis


def inbound() -> InboundGatewayMessage:
    return InboundGatewayMessage(
        request_id="REQ-1",
        message_id="MSG-1",
        channel_instance_id="sim-wa-serahs",
        provider="openwa-simulator",
        recipient_phone="+260976078440",
        customer_phone="+260971234567",
        text="I want braids",
        received_at=datetime(2026, 8, 2, 10, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_redis_gateway_queue_claim_ack_and_retry() -> None:
    redis = FakeRedis()
    queue = RedisReliableGatewayQueue(redis, RedisKeyspace("ntheemba", "test"))

    first_id = await queue.enqueue_inbound(inbound())
    claimed = await queue.claim_inbound("worker-1")
    assert claimed is not None
    assert claimed.delivery_id == first_id
    assert claimed.attempt == 1
    assert claimed.message.text == "I want braids"

    await queue.retry_inbound(claimed.delivery_id, claimed.consumer_id)
    retried = await queue.claim_inbound("worker-2")
    assert retried is not None
    assert retried.delivery_id != first_id
    assert retried.attempt == 2
    await queue.acknowledge_inbound(retried.delivery_id, retried.consumer_id)
    assert await queue.claim_inbound("worker-3") is None


@pytest.mark.asyncio
async def test_redis_gateway_queue_dead_letters_inbound() -> None:
    redis = FakeRedis()
    keyspace = RedisKeyspace("ntheemba", "test")
    queue = RedisReliableGatewayQueue(redis, keyspace)
    await queue.enqueue_inbound(inbound())
    claimed = await queue.claim_inbound("worker")
    assert claimed is not None

    await queue.dead_letter_inbound(claimed.delivery_id, "worker", "invalid business")

    entries = redis.streams[keyspace.gateway_inbound_dead_letter_stream()]
    assert len(entries) == 1
    assert entries[0][1]["reason"] == b"invalid business"


@pytest.mark.asyncio
async def test_redis_gateway_queue_outbound_uses_exact_channel() -> None:
    redis = FakeRedis()
    queue = RedisReliableGatewayQueue(redis, RedisKeyspace("ntheemba", "test"))
    message = OutboundGatewayMessage(
        reply_id="OUT-1",
        request_id="REQ-1",
        business_id="serahs-glow-lounge",
        channel_instance_id="sim-wa-serahs",
        recipient_phone="+260971234567",
        text="Which date suits you?",
    )

    await queue.enqueue_outbound(message)
    claimed = await queue.claim_outbound("sender-1")

    assert claimed is not None
    assert claimed.message.channel_instance_id == "sim-wa-serahs"
    assert claimed.message.business_id == "serahs-glow-lounge"
    await queue.acknowledge_outbound(claimed.delivery_id, "sender-1")


@pytest.mark.asyncio
async def test_redis_gateway_queue_reclaims_stale_pending_delivery() -> None:
    redis = FakeRedis()
    queue = RedisReliableGatewayQueue(
        redis,
        RedisKeyspace("ntheemba", "test"),
        claim_idle_seconds=1,
    )
    await queue.enqueue_inbound(inbound())
    first = await queue.claim_inbound("crashed-worker")
    assert first is not None

    recovered = await queue.claim_inbound("replacement-worker")

    assert recovered is not None
    assert recovered.delivery_id == first.delivery_id
    assert recovered.message.message_id == first.message.message_id
    await queue.acknowledge_inbound(recovered.delivery_id, recovered.consumer_id)


@pytest.mark.asyncio
async def test_redis_gateway_queue_preserves_platform_outbound_scope_without_fake_business() -> None:
    redis = FakeRedis()
    queue = RedisReliableGatewayQueue(redis, RedisKeyspace("ntheemba", "test"))
    message = OutboundGatewayMessage(
        reply_id="OUT-P1",
        request_id="REQ-P1",
        business_id="",
        channel_instance_id="platform-marketplace",
        recipient_phone="+260971234567",
        text="Marketplace results",
        scope=ChannelScope.PLATFORM,
        platform_role=ChannelRole.MARKETPLACE,
    )

    await queue.enqueue_outbound(message)
    claimed = await queue.claim_outbound("sender-platform")

    assert claimed is not None
    assert claimed.message.scope is ChannelScope.PLATFORM
    assert claimed.message.platform_role is ChannelRole.MARKETPLACE
    assert claimed.message.business_id == ""
    assert claimed.message.channel_instance_id == "platform-marketplace"
