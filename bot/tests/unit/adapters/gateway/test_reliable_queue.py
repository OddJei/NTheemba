"""Tests for non-destructive claim/ack/retry gateway semantics."""

from datetime import UTC, datetime

import pytest

from ntheemba.adapters.gateway import InMemoryReliableGatewayQueue
from ntheemba.domain.gateway import InboundGatewayMessage


def _message() -> InboundGatewayMessage:
    return InboundGatewayMessage(
        request_id="request-1",
        message_id="message-1",
        channel_instance_id="wa-1",
        provider="openwa",
        recipient_phone="+260970000001",
        customer_phone="+260970000111",
        text="Hello",
        received_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_claim_requires_ack_and_retry_preserves_delivery() -> None:
    queue = InMemoryReliableGatewayQueue()
    delivery_id = await queue.enqueue_inbound(_message())

    claimed = await queue.claim_inbound("worker-a")
    assert claimed is not None
    assert claimed.delivery_id == delivery_id
    assert claimed.attempt == 1
    assert await queue.claim_inbound("worker-b") is None

    await queue.retry_inbound(delivery_id, "worker-a")
    retried = await queue.claim_inbound("worker-b")
    assert retried is not None
    assert retried.attempt == 2

    await queue.acknowledge_inbound(delivery_id, "worker-b")
    assert await queue.claim_inbound("worker-c") is None
