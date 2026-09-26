"""Port and immutable command model for outgoing customer messages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol
from uuid import uuid4

from ntheemba.domain.business import ChannelRole, ChannelScope


class ReplyKind(StrEnum):
    """Supported outgoing content types for the first Ntheemba release."""

    TEXT = "text"
    IMAGE = "image"


@dataclass(frozen=True, slots=True)
class OutgoingMessage:
    """One ordered command for the WhatsApp gateway."""

    business_id: str
    customer_id: str
    conversation_id: str
    ordering_key: str
    idempotency_key: str
    kind: ReplyKind
    text: str | None = None
    image_url: str | None = None
    caption: str | None = None
    whatsapp_session_id: str = ""
    message_id: str = field(default_factory=lambda: f"OUT-{uuid4()}")
    metadata: Mapping[str, Any] = field(default_factory=dict)
    scope: ChannelScope = ChannelScope.BUSINESS
    platform_role: ChannelRole | None = None

    def __post_init__(self) -> None:
        required = {
            "customer_id": self.customer_id,
            "conversation_id": self.conversation_id,
            "ordering_key": self.ordering_key,
            "idempotency_key": self.idempotency_key,
            "message_id": self.message_id,
        }
        for name, value in required.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.scope is ChannelScope.BUSINESS:
            if not self.business_id.strip():
                raise ValueError("business replies require business_id")
            if self.platform_role is not None:
                raise ValueError("business replies cannot declare platform_role")
        else:
            if self.business_id.strip():
                raise ValueError("platform replies must not declare business_id")
            if self.platform_role is None:
                raise ValueError("platform replies require platform_role")

        if self.kind == ReplyKind.TEXT:
            if not self.text or not self.text.strip():
                raise ValueError("text replies require text")
            if self.image_url is not None:
                raise ValueError("text replies cannot contain image_url")
        elif self.kind == ReplyKind.IMAGE:
            if not self.image_url or not self.image_url.strip():
                raise ValueError("image replies require image_url")

        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class OutgoingPublisher(Protocol):
    """Publish ordered outgoing messages."""

    async def publish(self, message: OutgoingMessage) -> None:
        """Publish one message command."""

    async def publish_many(self, messages: tuple[OutgoingMessage, ...]) -> None:
        """Publish a sequence while preserving tuple order."""
