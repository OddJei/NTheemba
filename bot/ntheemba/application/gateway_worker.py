"""Acknowledged inbound and outbound gateway worker iterations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from ntheemba.application.failure_policy import FailureDisposition, classify_failure
from ntheemba.application.inbound_idempotency import InboundClaim, InboundMessageIdempotency

from ntheemba.application.service import ProcessingStatus
from ntheemba.domain.gateway import OutboundGatewayMessage
from ntheemba.observability.context import new_trace_context
from ntheemba.observability.tracer import Tracer
from ntheemba.ports.audit import AuditEvent, AuditSeverity, AuditSink
from ntheemba.ports.gateway import ReliableGatewayQueue


class WorkerAction(StrEnum):
    """Action taken for one claimed delivery."""

    IDLE = "idle"
    ACKNOWLEDGED = "acknowledged"
    RETRIED = "retried"
    DEAD_LETTERED = "dead_lettered"


@dataclass(frozen=True, slots=True)
class WorkerIterationResult:
    """Observable result of one worker iteration."""

    action: WorkerAction
    delivery_id: str = ""
    attempt: int = 0
    detail: str = ""


@dataclass(frozen=True, slots=True)
class WorkerRuntimeSnapshot:
    """Non-sensitive counters for one worker process."""

    acknowledged: int = 0
    duplicates: int = 0
    retried: int = 0
    dead_lettered: int = 0


class InboundGatewayProcessor(Protocol):
    """Provider-neutral application service that processes one inbound envelope."""

    async def process(self, message: Any) -> Any:
        """Return an object exposing a ProcessMessageOutcome as ``outcome``."""


class GatewayProviderSender(Protocol):
    """Provider adapter capable of sending one exact-channel reply."""

    async def send(self, message: OutboundGatewayMessage) -> None:
        """Send the message or raise when delivery failed."""


class InboundGatewayWorker:
    """Process one inbound queue item with ack/retry/dead-letter semantics."""

    def __init__(
        self,
        *,
        queue: ReliableGatewayQueue,
        service: InboundGatewayProcessor,
        consumer_id: str,
        max_attempts: int = 5,
        inbound_idempotency: InboundMessageIdempotency | None = None,
        audit: AuditSink | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        if not consumer_id.strip():
            raise ValueError("consumer_id must not be empty")
        if max_attempts < 1:
            raise ValueError("max_attempts must be greater than zero")
        self.queue = queue
        self.service = service
        self.consumer_id = consumer_id
        self.max_attempts = max_attempts
        self.inbound_idempotency = inbound_idempotency
        self.audit = audit
        self.tracer = tracer or Tracer()
        self._acknowledged = 0
        self._duplicates = 0
        self._retried = 0
        self._dead_lettered = 0

    def snapshot(self) -> WorkerRuntimeSnapshot:
        return WorkerRuntimeSnapshot(
            acknowledged=self._acknowledged,
            duplicates=self._duplicates,
            retried=self._retried,
            dead_lettered=self._dead_lettered,
        )

    async def run_once(self) -> WorkerIterationResult:
        claimed = await self.queue.claim_inbound(self.consumer_id)
        if claimed is None:
            return WorkerIterationResult(WorkerAction.IDLE)

        root = new_trace_context(
            request_id=claimed.message.request_id,
            message_id=claimed.message.message_id,
            attributes={
                "delivery_id": claimed.delivery_id,
                "attempt": claimed.attempt,
                "channel_instance_id": claimed.message.channel_instance_id,
                "provider": claimed.message.provider,
            },
        )
        ingress_claim: InboundClaim | None = None
        async with self.tracer.span(
            "gateway.inbound.delivery",
            "application.gateway_worker",
            root_context=root,
            attributes={"attempt": claimed.attempt},
        ):
            if self.inbound_idempotency is not None:
                ingress_claim = await self.inbound_idempotency.claim(
                    claimed.message,
                    owner_token=f"{self.consumer_id}:{claimed.delivery_id}",
                )
                if ingress_claim.duplicate:
                    await self.queue.acknowledge_inbound(
                        claimed.delivery_id, self.consumer_id
                    )
                    self._acknowledged += 1
                    self._duplicates += 1
                    await self._audit_worker_event(
                        claimed,
                        event_type="gateway.inbound.duplicate",
                        data={"action": WorkerAction.ACKNOWLEDGED.value},
                    )
                    return WorkerIterationResult(
                        WorkerAction.ACKNOWLEDGED,
                        claimed.delivery_id,
                        claimed.attempt,
                        "duplicate",
                    )

            try:
                routed = await self.service.process(claimed.message)
            except Exception as error:
                return await self._handle_failure(claimed, error, ingress_claim)

            outcome = routed.outcome
            if (
                outcome.status == ProcessingStatus.FAILED
                and outcome.error_code == "INFRASTRUCTURE_FAILED"
            ):
                return await self._handle_failure(
                    claimed,
                    RuntimeError(outcome.error_code),
                    ingress_claim,
                )

            await self.queue.acknowledge_inbound(claimed.delivery_id, self.consumer_id)
            if ingress_claim is not None:
                await self.inbound_idempotency.complete(
                    ingress_claim,
                    status=outcome.status.value,
                    request_id=outcome.request_id,
                )
            self._acknowledged += 1
            await self._audit_worker_event(
                claimed,
                event_type="gateway.inbound.acknowledged",
                data={
                    "action": WorkerAction.ACKNOWLEDGED.value,
                    "processing_status": outcome.status.value,
                },
            )
            return WorkerIterationResult(
                WorkerAction.ACKNOWLEDGED,
                claimed.delivery_id,
                claimed.attempt,
                outcome.status.value,
            )

    async def _handle_failure(
        self,
        claimed: Any,
        error: Exception,
        ingress_claim: InboundClaim | None,
    ) -> WorkerIterationResult:
        disposition = classify_failure(error)
        if disposition is FailureDisposition.DEAD_LETTER:
            if ingress_claim is not None:
                await self.inbound_idempotency.fail(
                    ingress_claim,
                    reason=type(error).__name__,
                    request_id=claimed.message.request_id,
                )
            return await self._dead_letter(
                claimed.delivery_id,
                claimed.attempt,
                error,
                claimed=claimed,
            )

        if claimed.attempt >= self.max_attempts:
            if ingress_claim is not None:
                await self.inbound_idempotency.fail(
                    ingress_claim,
                    reason=type(error).__name__,
                    request_id=claimed.message.request_id,
                )
            return await self._dead_letter(
                claimed.delivery_id,
                claimed.attempt,
                error,
                claimed=claimed,
            )

        if ingress_claim is not None:
            await self.inbound_idempotency.release(ingress_claim)
        await self.queue.retry_inbound(claimed.delivery_id, self.consumer_id)
        self._retried += 1
        await self._audit_worker_event(
            claimed,
            event_type="gateway.inbound.retried",
            severity=AuditSeverity.WARNING,
            data={
                "action": WorkerAction.RETRIED.value,
                "error_type": type(error).__name__,
            },
        )
        return WorkerIterationResult(
            WorkerAction.RETRIED,
            claimed.delivery_id,
            claimed.attempt,
            type(error).__name__,
        )

    async def _dead_letter(
        self,
        delivery_id: str,
        attempt: int,
        error: Exception,
        *,
        claimed: Any | None = None,
    ) -> WorkerIterationResult:
        reason = type(error).__name__
        await self.queue.dead_letter_inbound(delivery_id, self.consumer_id, reason)
        self._dead_lettered += 1
        if claimed is not None:
            await self._audit_worker_event(
                claimed,
                event_type="gateway.inbound.dead_lettered",
                severity=AuditSeverity.ERROR,
                data={
                    "action": WorkerAction.DEAD_LETTERED.value,
                    "error_type": reason,
                },
            )
        return WorkerIterationResult(
            WorkerAction.DEAD_LETTERED,
            delivery_id,
            attempt,
            reason,
        )

    async def _audit_worker_event(
        self,
        claimed: Any,
        *,
        event_type: str,
        data: dict[str, Any],
        severity: AuditSeverity = AuditSeverity.INFO,
    ) -> None:
        if self.audit is None:
            return
        try:
            await self.audit.record(
                AuditEvent(
                    event_type=event_type,
                    request_id=claimed.message.request_id,
                    business_id="__NTHEEMBA_GATEWAY__",
                    message_id=claimed.message.message_id,
                    severity=severity,
                    data={
                        "delivery_id": claimed.delivery_id,
                        "attempt": claimed.attempt,
                        "channel_instance_id": claimed.message.channel_instance_id,
                        "provider": claimed.message.provider,
                        **data,
                    },
                )
            )
        except Exception:
            return


class OutboundGatewayWorker:
    """Deliver one outgoing queue item through an exact-channel provider adapter."""

    def __init__(
        self,
        *,
        queue: ReliableGatewayQueue,
        sender: GatewayProviderSender,
        consumer_id: str,
        max_attempts: int = 5,
        audit: AuditSink | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        if not consumer_id.strip():
            raise ValueError("consumer_id must not be empty")
        if max_attempts < 1:
            raise ValueError("max_attempts must be greater than zero")
        self.queue = queue
        self.sender = sender
        self.consumer_id = consumer_id
        self.max_attempts = max_attempts
        self.audit = audit
        self.tracer = tracer or Tracer()
        self._acknowledged = 0
        self._duplicates = 0
        self._retried = 0
        self._dead_lettered = 0

    def snapshot(self) -> WorkerRuntimeSnapshot:
        return WorkerRuntimeSnapshot(
            acknowledged=self._acknowledged,
            duplicates=self._duplicates,
            retried=self._retried,
            dead_lettered=self._dead_lettered,
        )

    async def run_once(self) -> WorkerIterationResult:
        claimed = await self.queue.claim_outbound(self.consumer_id)
        if claimed is None:
            return WorkerIterationResult(WorkerAction.IDLE)

        root = new_trace_context(
            request_id=claimed.message.request_id,
            business_id=claimed.message.business_id,
            message_id=claimed.message.reply_id,
            attributes={
                "delivery_id": claimed.delivery_id,
                "attempt": claimed.attempt,
                "channel_instance_id": claimed.message.channel_instance_id,
                "scope": claimed.message.scope.value,
            },
        )
        async with self.tracer.span(
            "gateway.outbound.delivery",
            "application.gateway_worker",
            root_context=root,
            attributes={"attempt": claimed.attempt},
        ):
            try:
                await self.sender.send(claimed.message)
            except Exception as error:
                return await self._handle_failure(claimed, error)

            await self.queue.acknowledge_outbound(
                claimed.delivery_id, self.consumer_id
            )
            self._acknowledged += 1
            await self._audit_worker_event(
                claimed,
                event_type="gateway.outbound.sent",
                data={"action": WorkerAction.ACKNOWLEDGED.value},
            )
            return WorkerIterationResult(
                WorkerAction.ACKNOWLEDGED,
                claimed.delivery_id,
                claimed.attempt,
                "sent",
            )

    async def _handle_failure(
        self,
        claimed: Any,
        error: Exception,
    ) -> WorkerIterationResult:
        disposition = classify_failure(error)
        if (
            disposition is FailureDisposition.DEAD_LETTER
            or claimed.attempt >= self.max_attempts
        ):
            return await self._dead_letter(claimed, error)

        await self.queue.retry_outbound(claimed.delivery_id, self.consumer_id)
        self._retried += 1
        await self._audit_worker_event(
            claimed,
            event_type="gateway.outbound.retried",
            severity=AuditSeverity.WARNING,
            data={
                "action": WorkerAction.RETRIED.value,
                "error_type": type(error).__name__,
            },
        )
        return WorkerIterationResult(
            WorkerAction.RETRIED,
            claimed.delivery_id,
            claimed.attempt,
            type(error).__name__,
        )

    async def _dead_letter(
        self,
        claimed: Any,
        error: Exception,
    ) -> WorkerIterationResult:
        reason = type(error).__name__
        await self.queue.dead_letter_outbound(
            claimed.delivery_id, self.consumer_id, reason
        )
        self._dead_lettered += 1
        await self._audit_worker_event(
            claimed,
            event_type="gateway.outbound.dead_lettered",
            severity=AuditSeverity.ERROR,
            data={
                "action": WorkerAction.DEAD_LETTERED.value,
                "error_type": reason,
            },
        )
        return WorkerIterationResult(
            WorkerAction.DEAD_LETTERED,
            claimed.delivery_id,
            claimed.attempt,
            reason,
        )

    async def _audit_worker_event(
        self,
        claimed: Any,
        *,
        event_type: str,
        data: dict[str, Any],
        severity: AuditSeverity = AuditSeverity.INFO,
    ) -> None:
        if self.audit is None:
            return
        business_id = (
            claimed.message.business_id
            if claimed.message.business_id.strip()
            else "__NTHEEMBA_PLATFORM__"
        )
        try:
            await self.audit.record(
                AuditEvent(
                    event_type=event_type,
                    request_id=claimed.message.request_id,
                    business_id=business_id,
                    message_id=claimed.message.reply_id,
                    severity=severity,
                    data={
                        "delivery_id": claimed.delivery_id,
                        "attempt": claimed.attempt,
                        "channel_instance_id": claimed.message.channel_instance_id,
                        "scope": claimed.message.scope.value,
                        **data,
                    },
                )
            )
        except Exception:
            return
