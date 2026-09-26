"""Complete incoming-message orchestration pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from ntheemba.application.business_workflow_runtime import BusinessWorkflowRuntime
from ntheemba.application.runtime_context import BusinessExecutionContext
from ntheemba.application.session_coordinator import SessionCoordinator
from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowReply,
    WorkflowResult,
    WorkflowRouterPort,
)
from ntheemba.domain.business import ChannelRole, ChannelScope
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.enums import ConversationMode
from ntheemba.domain.intents import Intent
from ntheemba.domain.session import ConversationTurn, Session
from ntheemba.observability.context import new_trace_context
from ntheemba.observability.sanitization import redact_mapping
from ntheemba.observability.tracer import Tracer
from ntheemba.ports.audit import AuditEvent, AuditSeverity, AuditSink
from ntheemba.ports.publisher import OutgoingMessage, OutgoingPublisher
from ntheemba.ports.sessions import DeduplicationKey, DeduplicationStore


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _request_id() -> str:
    return f"REQ-{uuid4()}"


class ProcessingStatus(StrEnum):
    """Externally useful result of processing one incoming message."""

    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    SUPPRESSED = "suppressed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ProcessMessageCommand:
    """Trusted, normalized message command received from the API or worker."""

    business_id: str
    customer_id: str
    message_id: str
    text: str
    whatsapp_session_id: str = ""
    channel_instance_id: str = ""
    customer_phone: str = ""
    enabled_capabilities: frozenset[Capability] = frozenset()
    business_context: BusinessExecutionContext | None = None
    request_id: str = ""
    received_at: datetime | None = None
    reply_scope: ChannelScope = ChannelScope.BUSINESS
    reply_platform_role: ChannelRole | None = None
    expected_conversation_id: str = ""

    def __post_init__(self) -> None:
        for name, value in {
            "business_id": self.business_id,
            "customer_id": self.customer_id,
            "message_id": self.message_id,
            "text": self.text,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if len(self.text) > 4000:
            raise ValueError("text must not exceed 4000 characters")
        if self.received_at is not None and self.received_at.tzinfo is None:
            raise ValueError("received_at must be timezone-aware")
        if self.reply_scope is ChannelScope.BUSINESS and self.reply_platform_role is not None:
            raise ValueError("business reply scope cannot declare a platform role")
        if self.reply_scope is ChannelScope.PLATFORM and self.reply_platform_role is None:
            raise ValueError("platform reply scope requires a platform role")


@dataclass(frozen=True, slots=True)
class ProcessMessageOutcome:
    """Safe result returned to an API route or queue worker."""

    status: ProcessingStatus
    request_id: str
    conversation_id: str = ""
    published_message_ids: tuple[str, ...] = ()
    error_code: str = ""


class Interpreter(Protocol):
    """Interpret customer language into a typed intent proposal."""

    async def interpret(
        self,
        text: str,
        session: Session,
        *,
        capabilities: frozenset[Capability] = frozenset(),
    ) -> Intent:
        """Return one typed interpretation proposal."""


class InteractionRecorder(Protocol):
    """Best-effort persistence of post-workflow customer memory."""

    async def record_success(
        self,
        *,
        command: ProcessMessageCommand,
        session: Session,
        intent: Intent,
        result: WorkflowResult,
        published_message_ids: tuple[str, ...],
    ) -> None:
        """Record one successfully processed interaction."""


class ReplyLocalizer(Protocol):
    """Best-effort style-only localization of workflow replies."""

    async def localize_many(
        self,
        replies: tuple[WorkflowReply, ...],
    ) -> tuple[WorkflowReply, ...]:
        """Return localized replies or the originals when localization is unsafe."""


class NtheembaService:
    """Orchestrate deduplication, sessions, workflows, audit, and replies."""

    def __init__(
        self,
        *,
        coordinator: SessionCoordinator,
        deduplication: DeduplicationStore,
        interpreter: Interpreter,
        router: WorkflowRouterPort,
        publisher: OutgoingPublisher,
        audit: AuditSink,
        clock: Callable[[], datetime] = _utc_now,
        request_id_factory: Callable[[], str] = _request_id,
        deduplication_ttl: timedelta = timedelta(days=2),
        tracer: Tracer | None = None,
        interaction_recorder: InteractionRecorder | None = None,
        reply_localizer: ReplyLocalizer | None = None,
        failure_reply: str = (
            "I'm sorry, I could not complete that request. Please try again or ask for a person."
        ),
    ) -> None:
        if deduplication_ttl <= timedelta(0):
            raise ValueError("deduplication_ttl must be greater than zero")
        if not failure_reply.strip():
            raise ValueError("failure_reply must not be empty")
        self.coordinator = coordinator
        self.deduplication = deduplication
        self.interpreter = interpreter
        self.router = router
        self.workflow_runtime = BusinessWorkflowRuntime(router)
        self.publisher = publisher
        self.audit = audit
        self.clock = clock
        self.request_id_factory = request_id_factory
        self.deduplication_ttl = deduplication_ttl
        self.tracer = tracer or Tracer()
        self.interaction_recorder = interaction_recorder
        self.reply_localizer = reply_localizer
        self.failure_reply = failure_reply

    async def process_message(
        self,
        command: ProcessMessageCommand,
    ) -> ProcessMessageOutcome:
        """Process one normalized message exactly once while its claim is live."""

        request_id = command.request_id.strip() or self.request_id_factory()
        root_context = new_trace_context(
            request_id=request_id,
            business_id=command.business_id,
            message_id=command.message_id,
            attributes={"customer_id": command.customer_id},
        )
        async with self.tracer.span(
            "message.process",
            "application.service",
            root_context=root_context,
            attributes={"text_length": len(command.text)},
        ):
            return await self._process_claimed_message(command, request_id)

    async def _process_claimed_message(
        self,
        command: ProcessMessageCommand,
        request_id: str,
    ) -> ProcessMessageOutcome:
        dedup_key = DeduplicationKey(command.business_id, command.message_id)
        async with self.tracer.span(
            "message.deduplicate",
            "ports.deduplication",
        ):
            claimed = await self.deduplication.claim(
                dedup_key,
                ttl=self.deduplication_ttl,
            )
        if not claimed:
            await self._audit(
                AuditEvent(
                    event_type="message.duplicate",
                    request_id=request_id,
                    business_id=command.business_id,
                    message_id=command.message_id,
                )
            )
            return ProcessMessageOutcome(
                status=ProcessingStatus.DUPLICATE,
                request_id=request_id,
            )

        await self._audit(
            AuditEvent(
                event_type="message.accepted",
                request_id=request_id,
                business_id=command.business_id,
                message_id=command.message_id,
                data={"text_length": len(command.text)},
            )
        )

        try:
            async with self.tracer.span(
                "session.open",
                "application.session_coordinator",
            ):
                async with self.coordinator.open(
                    command.business_id,
                    command.customer_id,
                ) as managed:
                    if (
                        command.expected_conversation_id
                        and managed.session.conversation_id != command.expected_conversation_id
                    ):
                        await self._audit(
                            AuditEvent(
                                event_type="session.context_mismatch",
                                request_id=request_id,
                                business_id=command.business_id,
                                conversation_id=managed.session.conversation_id,
                                message_id=command.message_id,
                                severity=AuditSeverity.WARNING,
                                data={
                                    "expected_conversation_id": command.expected_conversation_id,
                                },
                            )
                        )
                        return ProcessMessageOutcome(
                            status=ProcessingStatus.FAILED,
                            request_id=request_id,
                            conversation_id=managed.session.conversation_id,
                            error_code="SESSION_CONTEXT_MISMATCH",
                        )
                    received_at = command.received_at or self.clock()
                    managed.append_turn(
                        ConversationTurn(
                            role="customer",
                            text=command.text,
                            message_id=command.message_id,
                            at=received_at,
                        )
                    )

                    if managed.session.mode == ConversationMode.HUMAN:
                        async with self.tracer.span(
                            "session.commit",
                            "ports.sessions",
                            attributes={"reason": "human_mode"},
                        ):
                            saved = await managed.commit()
                        await self._audit(
                            AuditEvent(
                                event_type="message.bot_suppressed",
                                request_id=request_id,
                                business_id=command.business_id,
                                conversation_id=saved.conversation_id,
                                message_id=command.message_id,
                                data={"reason": "human_mode"},
                            )
                        )
                        return ProcessMessageOutcome(
                            status=ProcessingStatus.SUPPRESSED,
                            request_id=request_id,
                            conversation_id=saved.conversation_id,
                        )

                    try:
                        async with self.tracer.span(
                            "message.interpret",
                            "services.interpretation",
                        ):
                            intent = await self.interpreter.interpret(
                                command.text,
                                managed.session,
                                capabilities=command.enabled_capabilities,
                            )
                        await self._audit(
                            AuditEvent(
                                event_type="intent.proposed",
                                request_id=request_id,
                                business_id=command.business_id,
                                conversation_id=managed.session.conversation_id,
                                message_id=command.message_id,
                                data={
                                    "intent": intent.type.value,
                                    "role": intent.role.value,
                                    "confidence": intent.confidence,
                                },
                            )
                        )
                        async with self.tracer.span(
                            "workflow.route",
                            "application.workflow_router",
                            attributes={"intent": intent.type.value},
                        ):
                            if command.business_context is not None:
                                result = await self.workflow_runtime.route(
                                    execution_context=command.business_context,
                                    session=managed.session,
                                    intent=intent,
                                    request_id=request_id,
                                    message_id=command.message_id,
                                    channel_instance_id=(
                                        command.channel_instance_id
                                        or command.whatsapp_session_id
                                    ),
                                )
                            else:
                                # Backward-compatible direct-service path for isolated tests.
                                result = await self.router.route(
                                    WorkflowContext(
                                        session=managed.session,
                                        intent=intent,
                                        business_id=command.business_id,
                                        customer_id=command.customer_id,
                                        request_id=request_id,
                                        message_id=command.message_id,
                                        capabilities=command.enabled_capabilities,
                                        channel_instance_id=(
                                            command.channel_instance_id
                                            or command.whatsapp_session_id
                                        ),
                                    )
                                )
                    except Exception as error:
                        managed.rollback()
                        managed.append_turn(
                            ConversationTurn(
                                role="customer",
                                text=command.text,
                                message_id=command.message_id,
                                at=received_at,
                            )
                        )
                        fallback = WorkflowReply.text_reply(self.failure_reply)
                        fallback_replies = await self._localize_replies((fallback,))
                        managed.append_turn(
                            ConversationTurn(
                                role="assistant",
                                text=fallback_replies[0].text or self.failure_reply,
                                at=self.clock(),
                            )
                        )
                        async with self.tracer.span(
                            "session.commit",
                            "ports.sessions",
                            attributes={"recovery": True},
                        ):
                            saved = await managed.commit()
                        await self._audit(
                            AuditEvent(
                                event_type="message.processing_failed",
                                request_id=request_id,
                                business_id=command.business_id,
                                conversation_id=saved.conversation_id,
                                message_id=command.message_id,
                                severity=AuditSeverity.ERROR,
                                data={"error_type": type(error).__name__},
                            )
                        )
                        published = await self._publish_replies(
                            command,
                            saved,
                            request_id,
                            fallback_replies,
                        )
                        return ProcessMessageOutcome(
                            status=ProcessingStatus.FAILED,
                            request_id=request_id,
                            conversation_id=saved.conversation_id,
                            published_message_ids=published,
                            error_code="PROCESSING_FAILED",
                        )

                    result = await self._localize_result(result)
                    self._append_assistant_history(managed.session, result)
                    if result.close_session:
                        managed.session.close()
                    async with self.tracer.span(
                        "session.commit",
                        "ports.sessions",
                    ):
                        saved = await managed.commit()
                    for event in result.events:
                        await self._audit(
                            AuditEvent(
                                event_type=event.event_type,
                                request_id=request_id,
                                business_id=command.business_id,
                                conversation_id=saved.conversation_id,
                                message_id=command.message_id,
                                data=event.data,
                            )
                        )

                    published = await self._publish_replies(
                        command,
                        saved,
                        request_id,
                        result.replies,
                    )
                    if self.interaction_recorder is not None:
                        try:
                            async with self.tracer.span(
                                "customer.remember",
                                "application.customer_memory",
                            ):
                                await self.interaction_recorder.record_success(
                                    command=command,
                                    session=saved,
                                    intent=intent,
                                    result=result,
                                    published_message_ids=published,
                                )
                        except Exception as error:
                            await self._audit(
                                AuditEvent(
                                    event_type="customer.memory_write_failed",
                                    request_id=request_id,
                                    business_id=command.business_id,
                                    conversation_id=saved.conversation_id,
                                    message_id=command.message_id,
                                    severity=AuditSeverity.WARNING,
                                    data={"error_type": type(error).__name__},
                                )
                            )
                    await self._audit(
                        AuditEvent(
                            event_type="message.processed",
                            request_id=request_id,
                            business_id=command.business_id,
                            conversation_id=saved.conversation_id,
                            message_id=command.message_id,
                            data={"reply_count": len(result.replies)},
                        )
                    )
                    return ProcessMessageOutcome(
                        status=ProcessingStatus.PROCESSED,
                        request_id=request_id,
                        conversation_id=saved.conversation_id,
                        published_message_ids=published,
                    )
        except Exception as error:
            async with self.tracer.span(
                "message.release_claim",
                "ports.deduplication",
            ):
                await self.deduplication.release(dedup_key)
            await self._audit(
                AuditEvent(
                    event_type="message.infrastructure_failed",
                    request_id=request_id,
                    business_id=command.business_id,
                    message_id=command.message_id,
                    severity=AuditSeverity.ERROR,
                    data={"error_type": type(error).__name__},
                )
            )
            return ProcessMessageOutcome(
                status=ProcessingStatus.FAILED,
                request_id=request_id,
                error_code="INFRASTRUCTURE_FAILED",
            )

    def _append_assistant_history(
        self,
        session: Session,
        result: WorkflowResult,
    ) -> None:
        for reply in result.replies:
            text = reply.text or reply.caption
            if text:
                session.append_history(
                    ConversationTurn(
                        role="assistant",
                        text=text,
                        at=self.clock(),
                    ),
                    maximum_entries=self.coordinator.history_limit,
                )

    async def _localize_result(self, result: WorkflowResult) -> WorkflowResult:
        replies = await self._localize_replies(result.replies)
        if replies is result.replies:
            return result
        return WorkflowResult(
            replies=replies,
            events=result.events,
            close_session=result.close_session,
        )

    async def _localize_replies(
        self,
        replies: tuple[WorkflowReply, ...],
    ) -> tuple[WorkflowReply, ...]:
        if self.reply_localizer is None or not replies:
            return replies
        try:
            return await self.reply_localizer.localize_many(replies)
        except Exception:
            return replies

    async def _publish_replies(
        self,
        command: ProcessMessageCommand,
        session: Session,
        request_id: str,
        replies: tuple[WorkflowReply, ...],
    ) -> tuple[str, ...]:
        messages = tuple(
            OutgoingMessage(
                business_id=(
                    command.business_id
                    if command.reply_scope is ChannelScope.BUSINESS
                    else ""
                ),
                customer_id=command.customer_id,
                conversation_id=session.conversation_id,
                ordering_key=session.conversation_id,
                idempotency_key=(f"{command.business_id}:{command.message_id}:reply:{index}"),
                kind=reply.publisher_kind,
                text=reply.text,
                image_url=reply.image_url,
                caption=reply.caption,
                whatsapp_session_id=(
                    command.channel_instance_id or command.whatsapp_session_id
                ),
                metadata={
                    "channel_instance_id": (
                        command.channel_instance_id or command.whatsapp_session_id
                    ),
                    "recipient_phone": command.customer_phone,
                    "target_business_id": command.business_id,
                    **dict(reply.metadata),
                    "request_id": request_id,
                },
                scope=command.reply_scope,
                platform_role=command.reply_platform_role,
            )
            for index, reply in enumerate(replies, start=1)
        )
        if messages:
            async with self.tracer.span(
                "reply.publish",
                "ports.publisher",
                attributes={"message_count": len(messages)},
            ):
                await self.publisher.publish_many(messages)
            await self._audit(
                AuditEvent(
                    event_type="outgoing.published",
                    request_id=request_id,
                    business_id=command.business_id,
                    conversation_id=session.conversation_id,
                    message_id=command.message_id,
                    data={"message_count": len(messages)},
                )
            )
        return tuple(message.message_id for message in messages)

    async def _audit(self, event: AuditEvent) -> None:
        """Treat audit storage as best effort during message delivery."""

        try:
            await self.audit.record(
                AuditEvent(
                    event_type=event.event_type,
                    request_id=event.request_id,
                    business_id=event.business_id,
                    severity=event.severity,
                    conversation_id=event.conversation_id,
                    message_id=event.message_id,
                    event_id=event.event_id,
                    occurred_at=event.occurred_at,
                    data=redact_mapping(event.data),
                )
            )
        except Exception:
            return
