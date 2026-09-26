"""Provider-neutral inbound routing across business and Ntheemba platform scopes."""

from __future__ import annotations

from dataclasses import dataclass

from ntheemba.application.capability_runtime import ChannelContextResolver
from ntheemba.application.customer_bridge import CustomerBridgeService
from ntheemba.application.gateway_service import GatewayMessageService, RoutedMessageOutcome
from ntheemba.application.marketplace import (
    PLATFORM_AUDIT_BUSINESS_ID,
    MarketplaceHandoffConsumptionService,
    MarketplaceOrderBridgeService,
    MarketplaceSelectionError,
)
from ntheemba.application.platform_session_coordinator import PlatformSessionCoordinator
from ntheemba.application.platform_workflow_runtime import (
    PlatformWorkflowAction,
    PlatformWorkflowRouter,
)
from ntheemba.application.service import (
    NtheembaService,
    ProcessMessageCommand,
    ProcessMessageOutcome,
    ProcessingStatus,
)
from ntheemba.application.workflow_router import WorkflowReply
from ntheemba.domain.business import ChannelScope, ResolvedBusinessContext, ResolvedPlatformContext
from ntheemba.domain.customers import PlatformCustomer
from ntheemba.domain.gateway import InboundGatewayMessage
from ntheemba.domain.platform_session import PlatformConversationStage
from ntheemba.ports.sessions import SessionKey
from ntheemba.ports.publisher import OutgoingMessage
from ntheemba.ports.audit import AuditEvent, AuditSink


@dataclass(frozen=True, slots=True)
class UnifiedRoutedMessageOutcome:
    """Safe generic result for either a business or platform inbound message."""

    outcome: ProcessMessageOutcome
    context: ResolvedBusinessContext | ResolvedPlatformContext
    customer: PlatformCustomer


class UnifiedGatewayMessageService:
    """Route exact channel identity before selecting business or platform execution."""

    def __init__(
        self,
        *,
        contexts: ChannelContextResolver,
        business_service: GatewayMessageService,
        customers: CustomerBridgeService,
        core: NtheembaService,
        platform_sessions: PlatformSessionCoordinator,
        platform_router: PlatformWorkflowRouter,
        handoff_consumption: MarketplaceHandoffConsumptionService,
        order_bridge: MarketplaceOrderBridgeService,
        audit: AuditSink | None = None,
    ) -> None:
        self.contexts = contexts
        self.business_service = business_service
        self.customers = customers
        self.core = core
        self.platform_sessions = platform_sessions
        self.platform_router = platform_router
        self.handoff_consumption = handoff_consumption
        self.order_bridge = order_bridge
        self.audit = audit

    async def process(
        self,
        message: InboundGatewayMessage,
    ) -> UnifiedRoutedMessageOutcome | RoutedMessageOutcome:
        context = await self.contexts.resolve(message)
        if isinstance(context, ResolvedBusinessContext):
            return await self.business_service.process(message)
        customer = await self.customers.resolve_platform_customer(message.customer_phone)
        outcome = await self._process_platform(message, context, customer)
        return UnifiedRoutedMessageOutcome(outcome, context, customer)

    async def _process_platform(
        self,
        message: InboundGatewayMessage,
        context: ResolvedPlatformContext,
        customer: PlatformCustomer,
    ) -> ProcessMessageOutcome:
        async with self.platform_sessions.open(
            context.channel.channel_instance_id,
            customer.customer_id,
        ) as managed:
            async with self.core.tracer.span(
                "platform.workflow.route",
                "application.platform_workflow_runtime",
                attributes={
                    "channel_instance_id": context.channel.channel_instance_id,
                    "role": context.role.value,
                    "stage": managed.session.stage.value,
                },
            ):
                routed = await self.platform_router.route(
                    context, managed.session, message.text
                )
            await self._audit_platform(
                message=message,
                context=context,
                conversation_id=managed.session.conversation_id,
                event_type="platform.workflow.routed",
                data={
                    "action": routed.action.value,
                    "stage": managed.session.stage.value,
                    "target_business_id": managed.session.target_business_id,
                },
            )
            if routed.action is PlatformWorkflowAction.BUSINESS_CONTINUE:
                try:
                    business_context = await self.handoff_consumption.consume(
                        context,
                        managed.session.handoff_id,
                    )
                except MarketplaceSelectionError:
                    managed.session.reset_marketplace()
                    saved = await managed.commit()
                    published = await self._publish_platform_replies(
                        message=message,
                        context=context,
                        customer=customer,
                        conversation_id=saved.conversation_id,
                        replies=(
                            WorkflowReply.text_reply(
                                "That business context changed. Please search Marketplace again."
                            ),
                        ),
                    )
                    return ProcessMessageOutcome(
                        status=ProcessingStatus.PROCESSED,
                        request_id=message.request_id,
                        conversation_id=saved.conversation_id,
                        published_message_ids=published,
                    )

                active_business = await self.core.coordinator.repository.load(
                    SessionKey(
                        business_context.business.business_id,
                        customer.customer_id,
                    )
                )
                if (
                    active_business is None
                    or active_business.conversation_id
                    != managed.session.business_conversation_id
                ):
                    managed.session.deactivate_business()
                    saved = await managed.commit()
                    published = await self._publish_platform_replies(
                        message=message,
                        context=context,
                        customer=customer,
                        conversation_id=saved.conversation_id,
                        replies=(
                            WorkflowReply.text_reply(
                                "The selected business session changed. Reply 'continue' "
                                "to re-enter it safely, or 'search again'."
                            ),
                        ),
                    )
                    return ProcessMessageOutcome(
                        status=ProcessingStatus.PROCESSED,
                        request_id=message.request_id,
                        conversation_id=saved.conversation_id,
                        published_message_ids=published,
                    )

                managed.session.touch()
                await managed.commit()
                outcome = await self.core.process_message(
                    ProcessMessageCommand(
                        business_id=business_context.business.business_id,
                        customer_id=customer.customer_id,
                        message_id=message.message_id,
                        text=message.text,
                        channel_instance_id=context.channel.channel_instance_id,
                        customer_phone=customer.phone_e164,
                        enabled_capabilities=business_context.capabilities,
                        business_context=business_context,
                        request_id=message.request_id,
                        received_at=message.received_at,
                        reply_scope=ChannelScope.PLATFORM,
                        reply_platform_role=context.role,
                        expected_conversation_id=managed.session.business_conversation_id,
                    )
                )
                if (
                    outcome.error_code == "SESSION_CONTEXT_MISMATCH"
                    and managed.session.stage is PlatformConversationStage.BUSINESS_ACTIVE
                ):
                    managed.session.deactivate_business()
                    await managed.commit()
                return outcome

            replies = routed.replies
            if routed.action is PlatformWorkflowAction.BUSINESS_ENTRY_READY:
                business_context = routed.business_context
                if business_context is None:
                    raise RuntimeError("business entry requires trusted handoff context")
                async with self.core.coordinator.open(
                    business_context.business.business_id,
                    customer.customer_id,
                ) as business_managed:
                    existing = business_managed.session
                    if not (
                        existing.flow.value == "idle"
                        and existing.stage.value == "start"
                    ) and existing.conversation_id != managed.session.business_conversation_id:
                        replies = (
                            WorkflowReply.text_reply(
                                "You already have an active conversation with this business. "
                                "Finish or cancel it before starting this Marketplace order."
                            ),
                        )
                        saved = await managed.commit()
                        published = await self._publish_platform_replies(
                            message=message,
                            context=context,
                            customer=customer,
                            conversation_id=saved.conversation_id,
                            replies=replies,
                        )
                        return ProcessMessageOutcome(
                            status=ProcessingStatus.PROCESSED,
                            request_id=message.request_id,
                            conversation_id=saved.conversation_id,
                            published_message_ids=published,
                        )
                    bridge = await self.order_bridge.start_order(
                        business_context,
                        customer_id=customer.customer_id,
                        request_id=message.request_id,
                        message_id=message.message_id,
                        session=business_managed.session,
                    )
                    business_managed.session = bridge.session
                    saved_business = await business_managed.commit()
                managed.session.activate_business(
                    business_id=business_context.business.business_id,
                    conversation_id=saved_business.conversation_id,
                )
                replies = replies + bridge.result.replies

            saved = await managed.commit()
            published = await self._publish_platform_replies(
                message=message,
                context=context,
                customer=customer,
                conversation_id=saved.conversation_id,
                replies=replies,
            )
            return ProcessMessageOutcome(
                status=ProcessingStatus.PROCESSED,
                request_id=message.request_id,
                conversation_id=saved.conversation_id,
                published_message_ids=published,
            )

    async def _audit_platform(
        self,
        *,
        message: InboundGatewayMessage,
        context: ResolvedPlatformContext,
        conversation_id: str,
        event_type: str,
        data: dict[str, object],
    ) -> None:
        if self.audit is None:
            return
        try:
            await self.audit.record(
                AuditEvent(
                    event_type=event_type,
                    request_id=message.request_id,
                    business_id=PLATFORM_AUDIT_BUSINESS_ID,
                    conversation_id=conversation_id,
                    message_id=message.message_id,
                    data={
                        "channel_instance_id": context.channel.channel_instance_id,
                        "role": context.role.value,
                        **data,
                    },
                )
            )
        except Exception:
            return

    async def _publish_platform_replies(
        self,
        *,
        message: InboundGatewayMessage,
        context: ResolvedPlatformContext,
        customer: PlatformCustomer,
        conversation_id: str,
        replies: tuple[WorkflowReply, ...],
    ) -> tuple[str, ...]:
        messages = tuple(
            OutgoingMessage(
                business_id="",
                customer_id=customer.customer_id,
                conversation_id=conversation_id,
                ordering_key=conversation_id,
                idempotency_key=(
                    f"platform:{context.channel.channel_instance_id}:"
                    f"{message.message_id}:reply:{index}"
                ),
                kind=reply.publisher_kind,
                text=reply.text,
                image_url=reply.image_url,
                caption=reply.caption,
                whatsapp_session_id=context.channel.channel_instance_id,
                metadata={
                    "channel_instance_id": context.channel.channel_instance_id,
                    "recipient_phone": customer.phone_e164,
                    "request_id": message.request_id,
                    **dict(reply.metadata),
                },
                scope=ChannelScope.PLATFORM,
                platform_role=context.role,
            )
            for index, reply in enumerate(replies, start=1)
        )
        if messages:
            await self.core.publisher.publish_many(messages)
        return tuple(item.message_id for item in messages)
