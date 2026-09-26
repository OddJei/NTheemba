"""Acknowledged in-memory gateway queue used before Redis Streams."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from uuid import uuid4

from ntheemba.domain.gateway import InboundGatewayMessage, OutboundGatewayMessage
from ntheemba.ports.gateway import ClaimedInboundMessage, ClaimedOutboundMessage


@dataclass(slots=True)
class _InboundDelivery:
    message: InboundGatewayMessage
    attempt: int = 0
    consumer_id: str = ""


@dataclass(slots=True)
class _OutboundDelivery:
    message: OutboundGatewayMessage
    attempt: int = 0
    consumer_id: str = ""


class InMemoryReliableGatewayQueue:
    """Model claim/ack/retry behavior without unsafe destructive pops."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._inbound_pending: deque[str] = deque()
        self._inbound: dict[str, _InboundDelivery] = {}
        self._outbound_pending: deque[str] = deque()
        self._outbound: dict[str, _OutboundDelivery] = {}
        self.inbound_dead_letters: dict[str, tuple[InboundGatewayMessage, str]] = {}
        self.outbound_dead_letters: dict[str, tuple[OutboundGatewayMessage, str]] = {}

    async def enqueue_inbound(self, message: InboundGatewayMessage) -> str:
        async with self._lock:
            delivery_id = f"GIN-{uuid4()}"
            self._inbound[delivery_id] = _InboundDelivery(message)
            self._inbound_pending.append(delivery_id)
            return delivery_id

    async def claim_inbound(self, consumer_id: str) -> ClaimedInboundMessage | None:
        if not consumer_id.strip():
            raise ValueError("consumer_id must not be empty")
        async with self._lock:
            while self._inbound_pending:
                delivery_id = self._inbound_pending.popleft()
                delivery = self._inbound.get(delivery_id)
                if delivery is None or delivery.consumer_id:
                    continue
                delivery.consumer_id = consumer_id
                delivery.attempt += 1
                return ClaimedInboundMessage(
                    delivery_id,
                    consumer_id,
                    delivery.message,
                    delivery.attempt,
                )
            return None

    async def acknowledge_inbound(self, delivery_id: str, consumer_id: str) -> None:
        async with self._lock:
            self._owned_inbound(delivery_id, consumer_id)
            self._inbound.pop(delivery_id)

    async def retry_inbound(self, delivery_id: str, consumer_id: str) -> None:
        async with self._lock:
            delivery = self._owned_inbound(delivery_id, consumer_id)
            delivery.consumer_id = ""
            self._inbound_pending.append(delivery_id)

    async def dead_letter_inbound(
        self,
        delivery_id: str,
        consumer_id: str,
        reason: str,
    ) -> None:
        if not reason.strip():
            raise ValueError("reason must not be empty")
        async with self._lock:
            delivery = self._owned_inbound(delivery_id, consumer_id)
            self.inbound_dead_letters[delivery_id] = (delivery.message, reason)
            self._inbound.pop(delivery_id)

    async def enqueue_outbound(self, message: OutboundGatewayMessage) -> str:
        async with self._lock:
            delivery_id = f"GOUT-{uuid4()}"
            self._outbound[delivery_id] = _OutboundDelivery(message)
            self._outbound_pending.append(delivery_id)
            return delivery_id

    async def claim_outbound(
        self, consumer_id: str, gateway_id: str = ""
    ) -> ClaimedOutboundMessage | None:
        if not consumer_id.strip():
            raise ValueError("consumer_id must not be empty")
        async with self._lock:
            remaining = len(self._outbound_pending)
            while remaining:
                remaining -= 1
                delivery_id = self._outbound_pending.popleft()
                delivery = self._outbound.get(delivery_id)
                if delivery is None or delivery.consumer_id:
                    continue
                if gateway_id and delivery.message.gateway_id != gateway_id.strip().casefold():
                    self._outbound_pending.append(delivery_id)
                    continue
                delivery.consumer_id = consumer_id
                delivery.attempt += 1
                return ClaimedOutboundMessage(
                    delivery_id,
                    consumer_id,
                    delivery.message,
                    delivery.attempt,
                )
            return None

    async def acknowledge_outbound(
        self, delivery_id: str, consumer_id: str, gateway_id: str = ""
    ) -> None:
        async with self._lock:
            delivery = self._owned_outbound(delivery_id, consumer_id)
            self._validate_gateway(delivery, gateway_id)
            self._outbound.pop(delivery_id)

    async def retry_outbound(
        self, delivery_id: str, consumer_id: str, gateway_id: str = ""
    ) -> None:
        async with self._lock:
            delivery = self._owned_outbound(delivery_id, consumer_id)
            self._validate_gateway(delivery, gateway_id)
            delivery.consumer_id = ""
            self._outbound_pending.append(delivery_id)

    async def dead_letter_outbound(
        self,
        delivery_id: str,
        consumer_id: str,
        reason: str,
        gateway_id: str = "",
    ) -> None:
        if not reason.strip():
            raise ValueError("reason must not be empty")
        async with self._lock:
            delivery = self._owned_outbound(delivery_id, consumer_id)
            self._validate_gateway(delivery, gateway_id)
            self.outbound_dead_letters[delivery_id] = (delivery.message, reason)
            self._outbound.pop(delivery_id)

    def _owned_inbound(self, delivery_id: str, consumer_id: str) -> _InboundDelivery:
        delivery = self._inbound.get(delivery_id)
        if delivery is None:
            raise LookupError(delivery_id)
        if delivery.consumer_id != consumer_id:
            raise PermissionError("inbound delivery is not owned by this consumer")
        return delivery

    def _owned_outbound(self, delivery_id: str, consumer_id: str) -> _OutboundDelivery:
        delivery = self._outbound.get(delivery_id)
        if delivery is None:
            raise LookupError(delivery_id)
        if delivery.consumer_id != consumer_id:
            raise PermissionError("outbound delivery is not owned by this consumer")
        return delivery

    @staticmethod
    def _validate_gateway(delivery: _OutboundDelivery, gateway_id: str) -> None:
        if gateway_id and delivery.message.gateway_id != gateway_id.strip().casefold():
            raise PermissionError("outbound delivery belongs to another gateway")
