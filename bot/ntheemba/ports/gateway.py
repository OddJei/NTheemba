"""Reliable gateway queue contracts with explicit acknowledgement semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ntheemba.domain.gateway import InboundGatewayMessage, OutboundGatewayMessage


@dataclass(frozen=True, slots=True)
class ClaimedInboundMessage:
    """One inbound delivery owned temporarily by a consumer."""

    delivery_id: str
    consumer_id: str
    message: InboundGatewayMessage
    attempt: int

    def __post_init__(self) -> None:
        if not self.delivery_id.strip() or not self.consumer_id.strip():
            raise ValueError("delivery_id and consumer_id must not be empty")
        if self.attempt <= 0:
            raise ValueError("attempt must be greater than zero")


@dataclass(frozen=True, slots=True)
class ClaimedOutboundMessage:
    """One outgoing delivery owned temporarily by a sender worker."""

    delivery_id: str
    consumer_id: str
    message: OutboundGatewayMessage
    attempt: int

    def __post_init__(self) -> None:
        if not self.delivery_id.strip() or not self.consumer_id.strip():
            raise ValueError("delivery_id and consumer_id must not be empty")
        if self.attempt <= 0:
            raise ValueError("attempt must be greater than zero")


class ReliableGatewayQueue(Protocol):
    """Queue contract suitable for Redis Streams in Phase 12."""

    async def enqueue_inbound(self, message: InboundGatewayMessage) -> str:
        """Append an inbound message and return its delivery ID."""

    async def claim_inbound(self, consumer_id: str) -> ClaimedInboundMessage | None:
        """Claim one pending inbound message without removing it permanently."""

    async def acknowledge_inbound(self, delivery_id: str, consumer_id: str) -> None:
        """Acknowledge successful processing."""

    async def retry_inbound(self, delivery_id: str, consumer_id: str) -> None:
        """Return a failed delivery to the pending queue."""

    async def dead_letter_inbound(
        self,
        delivery_id: str,
        consumer_id: str,
        reason: str,
    ) -> None:
        """Move an unrecoverable delivery to a dead-letter collection."""

    async def enqueue_outbound(self, message: OutboundGatewayMessage) -> str:
        """Append an outgoing message and return its delivery ID."""

    async def claim_outbound(
        self, consumer_id: str, gateway_id: str = ""
    ) -> ClaimedOutboundMessage | None:
        """Claim one outgoing delivery."""

    async def acknowledge_outbound(
        self, delivery_id: str, consumer_id: str, gateway_id: str = ""
    ) -> None:
        """Acknowledge successful provider delivery."""

    async def retry_outbound(
        self, delivery_id: str, consumer_id: str, gateway_id: str = ""
    ) -> None:
        """Return an outgoing delivery to pending state."""

    async def dead_letter_outbound(
        self,
        delivery_id: str,
        consumer_id: str,
        reason: str,
        gateway_id: str = "",
    ) -> None:
        """Move an unrecoverable outgoing delivery to a dead-letter collection."""
