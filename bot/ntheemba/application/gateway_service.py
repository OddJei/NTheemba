"""Provider-neutral inbound routing into the existing Ntheemba service."""

from __future__ import annotations

from dataclasses import dataclass

from ntheemba.application.capability_runtime import BusinessContextResolver
from ntheemba.application.customer_bridge import CustomerBridgeService
from ntheemba.application.runtime_context import bind_runtime_context
from ntheemba.application.service import (
    NtheembaService,
    ProcessMessageCommand,
    ProcessMessageOutcome,
)
from ntheemba.domain.business import ResolvedBusinessContext
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.customers import PlatformCustomer
from ntheemba.domain.gateway import InboundGatewayMessage
from ntheemba.observability.context import new_trace_context
from ntheemba.observability.tracer import Tracer


@dataclass(frozen=True, slots=True)
class RoutedMessageOutcome:
    """Result plus the trusted routing/customer context used for processing."""

    outcome: ProcessMessageOutcome
    business: ResolvedBusinessContext
    customer: PlatformCustomer


class GatewayMessageService:
    """Resolve channel and customer before invoking interpretation and workflows."""

    def __init__(
        self,
        *,
        businesses: BusinessContextResolver,
        customers: CustomerBridgeService,
        core: NtheembaService,
        tracer: Tracer | None = None,
    ) -> None:
        self.businesses = businesses
        self.customers = customers
        self.core = core
        self.tracer = tracer or core.tracer

    async def process(self, message: InboundGatewayMessage) -> RoutedMessageOutcome:
        root = new_trace_context(
            request_id=message.request_id,
            message_id=message.message_id,
            attributes={
                "channel_instance_id": message.channel_instance_id,
                "provider": message.provider,
            },
        )
        async with self.tracer.span(
            "gateway.message",
            "application.gateway_service",
            root_context=root,
        ):
            business = await self.businesses.resolve(message)
            async with self.tracer.span(
                "customer.resolve",
                "application.customer_bridge",
                attributes={"business_id": business.business.business_id},
            ):
                customer = await self.customers.resolve_platform_customer(
                    message.customer_phone
                )
                if Capability.CLIENT_IDENTIFY in business.capabilities:
                    # Client lookup is an integration call and therefore needs the same
                    # trusted tenant context that workflow execution receives later.
                    with bind_runtime_context(business):
                        await self.customers.resolve_business_client(
                            business_id=business.business.business_id,
                            customer_id=customer.customer_id,
                        )
            outcome = await self.core.process_message(
                ProcessMessageCommand(
                    business_id=business.business.business_id,
                    customer_id=customer.customer_id,
                    message_id=message.message_id,
                    text=message.text,
                    whatsapp_session_id=business.channel.channel_instance_id,
                    channel_instance_id=business.channel.channel_instance_id,
                    customer_phone=customer.phone_e164,
                    enabled_capabilities=business.capabilities,
                    business_context=business,
                    request_id=message.request_id,
                    received_at=message.received_at,
                )
            )
        return RoutedMessageOutcome(outcome, business, customer)
