"""N19-N21 generic idempotency, resilience, and worker observability gates."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from ntheemba.adapters.gateway.in_memory import InMemoryReliableGatewayQueue
from ntheemba.adapters.ncpc.http import NCPCResponseError, NCPCUnavailableError
from ntheemba.adapters.tracing.in_memory import InMemoryTraceSink
from ntheemba.application.gateway_worker import (
    InboundGatewayWorker,
    OutboundGatewayWorker,
    WorkerAction,
)
from ntheemba.application.inbound_idempotency import InboundMessageIdempotency
from ntheemba.application.service import ProcessingStatus
from ntheemba.domain.business import ChannelRole, ChannelScope
from ntheemba.domain.gateway import InboundGatewayMessage, OutboundGatewayMessage
from ntheemba.infrastructure.memory.audit import MemoryAuditSink
from ntheemba.infrastructure.memory.idempotency import MemoryIdempotencyStore
from ntheemba.observability.tracer import Tracer


def inbound(*, message_id: str = "MSG-1") -> InboundGatewayMessage:
    return InboundGatewayMessage(
        request_id=f"REQ-{message_id}",
        message_id=message_id,
        channel_instance_id="ntheemba-marketplace-primary",
        provider="waha-future-adapter",
        recipient_phone="+260970000000",
        customer_phone="+260971234567",
        text="find cooking oil",
        received_at=datetime(2026, 9, 4, 17, 0, tzinfo=UTC),
    )


def outbound() -> OutboundGatewayMessage:
    return OutboundGatewayMessage(
        reply_id="OUT-1",
        request_id="REQ-OUT-1",
        business_id="",
        channel_instance_id="ntheemba-marketplace-primary",
        recipient_phone="+260971234567",
        text="I found two options.",
        scope=ChannelScope.PLATFORM,
        platform_role=ChannelRole.MARKETPLACE,
    )


class SequencedService:
    def __init__(self, *steps: Exception | ProcessingStatus) -> None:
        self.steps = list(steps) or [ProcessingStatus.PROCESSED]
        self.calls = 0

    async def process(self, message: InboundGatewayMessage):
        self.calls += 1
        step = self.steps.pop(0) if self.steps else ProcessingStatus.PROCESSED
        if isinstance(step, Exception):
            raise step
        return SimpleNamespace(
            outcome=SimpleNamespace(
                status=step,
                error_code="",
                request_id=message.request_id,
            )
        )


class SequencedSender:
    def __init__(self, *errors: Exception | None) -> None:
        self.errors = list(errors)
        self.sent: list[OutboundGatewayMessage] = []

    async def send(self, message: OutboundGatewayMessage) -> None:
        error = self.errors.pop(0) if self.errors else None
        if error is not None:
            raise error
        self.sent.append(message)


def ingress(store: MemoryIdempotencyStore) -> InboundMessageIdempotency:
    return InboundMessageIdempotency(store, ttl=timedelta(days=7))


@pytest.mark.asyncio
async def test_generic_ingress_deduplicates_platform_messages_before_workflow() -> None:
    queue = InMemoryReliableGatewayQueue()
    message = inbound()
    await queue.enqueue_inbound(message)
    await queue.enqueue_inbound(message)
    service = SequencedService()
    worker = InboundGatewayWorker(
        queue=queue,
        service=service,  # type: ignore[arg-type]
        consumer_id="worker-1",
        inbound_idempotency=ingress(MemoryIdempotencyStore()),
    )

    first = await worker.run_once()
    duplicate = await worker.run_once()

    assert first.action is WorkerAction.ACKNOWLEDGED
    assert duplicate.action is WorkerAction.ACKNOWLEDGED
    assert duplicate.detail == "duplicate"
    assert service.calls == 1


@pytest.mark.asyncio
async def test_retryable_failure_releases_ingress_claim_then_completes_once() -> None:
    queue = InMemoryReliableGatewayQueue()
    message = inbound()
    await queue.enqueue_inbound(message)
    store = MemoryIdempotencyStore()
    service = SequencedService(
        NCPCUnavailableError("NCPC temporarily unavailable"),
        ProcessingStatus.PROCESSED,
    )
    worker = InboundGatewayWorker(
        queue=queue,
        service=service,  # type: ignore[arg-type]
        consumer_id="worker-1",
        max_attempts=3,
        inbound_idempotency=ingress(store),
    )

    first = await worker.run_once()
    second = await worker.run_once()
    await queue.enqueue_inbound(message)
    duplicate = await worker.run_once()

    assert first.action is WorkerAction.RETRIED
    assert second.action is WorkerAction.ACKNOWLEDGED
    assert duplicate.detail == "duplicate"
    assert service.calls == 2


@pytest.mark.asyncio
async def test_non_retryable_downstream_contract_failure_is_dead_lettered_once() -> None:
    queue = InMemoryReliableGatewayQueue()
    message = inbound()
    await queue.enqueue_inbound(message)
    service = SequencedService(NCPCResponseError("malformed response"))
    worker = InboundGatewayWorker(
        queue=queue,
        service=service,  # type: ignore[arg-type]
        consumer_id="worker-1",
        max_attempts=5,
        inbound_idempotency=ingress(MemoryIdempotencyStore()),
    )

    terminal = await worker.run_once()
    await queue.enqueue_inbound(message)
    duplicate = await worker.run_once()

    assert terminal.action is WorkerAction.DEAD_LETTERED
    assert terminal.attempt == 1
    assert duplicate.detail == "duplicate"
    assert service.calls == 1


@pytest.mark.asyncio
async def test_inbound_worker_emits_correlated_audit_and_trace_events() -> None:
    queue = InMemoryReliableGatewayQueue()
    await queue.enqueue_inbound(inbound())
    audit = MemoryAuditSink()
    traces = InMemoryTraceSink()
    worker = InboundGatewayWorker(
        queue=queue,
        service=SequencedService(),  # type: ignore[arg-type]
        consumer_id="worker-1",
        inbound_idempotency=ingress(MemoryIdempotencyStore()),
        audit=audit,
        tracer=Tracer(traces),
    )

    result = await worker.run_once()
    events = await traces.snapshot()

    assert result.action is WorkerAction.ACKNOWLEDGED
    assert [event.event_type for event in audit.events] == [
        "gateway.inbound.acknowledged"
    ]
    assert audit.events[0].request_id == "REQ-MSG-1"
    assert audit.events[0].data["channel_instance_id"] == "ntheemba-marketplace-primary"
    assert any(event.node_id == "gateway.inbound.delivery" for event in events)
    assert all("+260" not in str(dict(event.attributes)) for event in events)


@pytest.mark.asyncio
async def test_outbound_worker_audits_retry_and_platform_delivery_without_fake_business() -> None:
    queue = InMemoryReliableGatewayQueue()
    await queue.enqueue_outbound(outbound())
    audit = MemoryAuditSink()
    sender = SequencedSender(ConnectionError("provider down"), None)
    worker = OutboundGatewayWorker(
        queue=queue,
        sender=sender,
        consumer_id="sender-1",
        max_attempts=3,
        audit=audit,
    )

    first = await worker.run_once()
    second = await worker.run_once()

    assert first.action is WorkerAction.RETRIED
    assert second.action is WorkerAction.ACKNOWLEDGED
    assert [event.event_type for event in audit.events] == [
        "gateway.outbound.retried",
        "gateway.outbound.sent",
    ]
    assert all(event.business_id == "__NTHEEMBA_PLATFORM__" for event in audit.events)
    assert sender.sent == [outbound()]


class FailingAuditSink:
    async def record(self, _event) -> None:
        raise RuntimeError("audit unavailable")

    async def record_many(self, _events) -> None:
        raise RuntimeError("audit unavailable")


@pytest.mark.asyncio
async def test_worker_audit_failure_is_fail_open_and_counters_remain_correct() -> None:
    queue = InMemoryReliableGatewayQueue()
    message = inbound()
    await queue.enqueue_inbound(message)
    await queue.enqueue_inbound(message)
    worker = InboundGatewayWorker(
        queue=queue,
        service=SequencedService(),  # type: ignore[arg-type]
        consumer_id="worker-1",
        inbound_idempotency=ingress(MemoryIdempotencyStore()),
        audit=FailingAuditSink(),  # type: ignore[arg-type]
    )

    first = await worker.run_once()
    second = await worker.run_once()
    snapshot = worker.snapshot()

    assert first.action is WorkerAction.ACKNOWLEDGED
    assert second.detail == "duplicate"
    assert snapshot.acknowledged == 2
    assert snapshot.duplicates == 1
    assert snapshot.retried == 0
    assert snapshot.dead_lettered == 0
