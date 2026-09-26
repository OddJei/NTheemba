"""Gateway worker acknowledgement, retry, and dead-letter tests."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from ntheemba.adapters.gateway.in_memory import InMemoryReliableGatewayQueue
from ntheemba.application.capability_runtime import UnknownBusinessChannelError
from ntheemba.application.gateway_worker import (
    InboundGatewayWorker,
    OutboundGatewayWorker,
    WorkerAction,
)
from ntheemba.application.service import ProcessingStatus
from ntheemba.domain.gateway import InboundGatewayMessage, OutboundGatewayMessage


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


def outbound() -> OutboundGatewayMessage:
    return OutboundGatewayMessage(
        reply_id="OUT-1",
        request_id="REQ-1",
        business_id="serahs-glow-lounge",
        channel_instance_id="sim-wa-serahs",
        recipient_phone="+260971234567",
        text="Which date suits you?",
    )


class StubGatewayService:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        status=ProcessingStatus.PROCESSED,
        error_code: str = "",
    ) -> None:
        self.error = error
        self.status = status
        self.error_code = error_code

    async def process(self, _message: InboundGatewayMessage):
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            outcome=SimpleNamespace(status=self.status, error_code=self.error_code)
        )


class StubSender:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.sent: list[OutboundGatewayMessage] = []

    async def send(self, message: OutboundGatewayMessage) -> None:
        if self.failures:
            self.failures -= 1
            raise ConnectionError("provider unavailable")
        self.sent.append(message)


@pytest.mark.asyncio
async def test_inbound_worker_acknowledges_processed_delivery() -> None:
    queue = InMemoryReliableGatewayQueue()
    await queue.enqueue_inbound(inbound())
    worker = InboundGatewayWorker(
        queue=queue,
        service=StubGatewayService(),  # type: ignore[arg-type]
        consumer_id="worker-1",
    )

    result = await worker.run_once()

    assert result.action == WorkerAction.ACKNOWLEDGED
    assert await queue.claim_inbound("worker-2") is None


@pytest.mark.asyncio
async def test_inbound_worker_retries_infrastructure_failure_then_dead_letters() -> None:
    queue = InMemoryReliableGatewayQueue()
    await queue.enqueue_inbound(inbound())
    worker = InboundGatewayWorker(
        queue=queue,
        service=StubGatewayService(  # type: ignore[arg-type]
            status=ProcessingStatus.FAILED,
            error_code="INFRASTRUCTURE_FAILED",
        ),
        consumer_id="worker-1",
        max_attempts=2,
    )

    first = await worker.run_once()
    second = await worker.run_once()

    assert first.action == WorkerAction.RETRIED
    assert second.action == WorkerAction.DEAD_LETTERED
    assert len(queue.inbound_dead_letters) == 1


@pytest.mark.asyncio
async def test_inbound_worker_dead_letters_unknown_business_without_retry() -> None:
    queue = InMemoryReliableGatewayQueue()
    await queue.enqueue_inbound(inbound())
    worker = InboundGatewayWorker(
        queue=queue,
        service=StubGatewayService(  # type: ignore[arg-type]
            error=UnknownBusinessChannelError("unknown-channel")
        ),
        consumer_id="worker-1",
    )

    result = await worker.run_once()

    assert result.action == WorkerAction.DEAD_LETTERED
    assert len(queue.inbound_dead_letters) == 1


@pytest.mark.asyncio
async def test_outbound_worker_retries_and_preserves_exact_channel() -> None:
    queue = InMemoryReliableGatewayQueue()
    await queue.enqueue_outbound(outbound())
    sender = StubSender(failures=1)
    worker = OutboundGatewayWorker(
        queue=queue,
        sender=sender,
        consumer_id="sender-1",
        max_attempts=3,
    )

    first = await worker.run_once()
    second = await worker.run_once()

    assert first.action == WorkerAction.RETRIED
    assert second.action == WorkerAction.ACKNOWLEDGED
    assert sender.sent[0].channel_instance_id == "sim-wa-serahs"
