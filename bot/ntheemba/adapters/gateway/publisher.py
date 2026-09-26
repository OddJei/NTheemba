"""Outgoing publisher backed by the reliable gateway queue and idempotency."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from ntheemba.domain.gateway import OutboundGatewayMessage
from ntheemba.ports.businesses import BusinessRegistry
from ntheemba.ports.gateway import ReliableGatewayQueue
from ntheemba.ports.idempotency import IdempotencyStatus, IdempotencyStore
from ntheemba.ports.publisher import OutgoingMessage


class ReliableGatewayPublisher:
    def __init__(
        self,
        queue: ReliableGatewayQueue,
        idempotency: IdempotencyStore,
        registry: BusinessRegistry,
        *,
        ttl: timedelta,
        transport_gateway_ids: frozenset[str] = frozenset(),
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("ttl must be greater than zero")
        self.queue = queue
        self.idempotency = idempotency
        self.registry = registry
        self.ttl = ttl
        self.transport_gateway_ids = frozenset(
            item.strip().casefold() for item in transport_gateway_ids if item.strip()
        )

    async def publish(self, message: OutgoingMessage) -> None:
        key = f"gateway-reply:{message.idempotency_key}"
        owner = f"PUB-{uuid4()}"
        claimed = await self.idempotency.claim(key, owner_token=owner, ttl=self.ttl)
        if not claimed:
            current = await self.idempotency.get(key)
            if current is not None and current.status == IdempotencyStatus.COMPLETED:
                return
            raise RuntimeError("outgoing reply is already being published")
        try:
            channel = str(
                message.metadata.get("channel_instance_id")
                or message.whatsapp_session_id
            ).strip()
            recipient = str(message.metadata.get("recipient_phone") or "").strip()
            if not channel or not recipient:
                raise ValueError("outgoing message requires exact channel and recipient phone")
            binding = await self.registry.get_channel(channel)
            if binding is None or not binding.enabled:
                raise ValueError("outgoing message requires an enabled registered channel")
            text = message.text or message.caption or ""
            delivery_id = await self.queue.enqueue_outbound(
                OutboundGatewayMessage(
                    reply_id=message.message_id,
                    request_id=str(message.metadata.get("request_id") or message.message_id),
                    business_id=message.business_id,
                    channel_instance_id=channel,
                    recipient_phone=recipient,
                    text=text,
                    gateway_id=(
                        binding.provider
                        if binding.provider in self.transport_gateway_ids
                        else ""
                    ),
                    delivery_target=recipient,
                    metadata={
                        "conversation_id": message.conversation_id,
                        "kind": message.kind.value,
                        "image_url": message.image_url or "",
                        "idempotency_key": message.idempotency_key,
                    },
                    scope=message.scope,
                    platform_role=message.platform_role,
                )
            )
            await self.idempotency.complete(
                key,
                owner_token=owner,
                result={"delivery_id": delivery_id},
                ttl=self.ttl,
            )
        except Exception:
            await self.idempotency.release(key, owner_token=owner)
            raise

    async def publish_many(self, messages: tuple[OutgoingMessage, ...]) -> None:
        for message in messages:
            await self.publish(message)
