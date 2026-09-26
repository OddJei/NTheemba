"""Stable inbound and outbound gateway envelopes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from ntheemba.domain.business import ChannelRole, ChannelScope
from ntheemba.domain.customers import normalize_phone_e164


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class InboundGatewayMessage:
    """Provider-neutral inbound message before business and customer resolution."""

    request_id: str
    message_id: str
    channel_instance_id: str
    provider: str
    recipient_phone: str
    customer_phone: str
    text: str
    received_at: datetime = field(default_factory=_utc_now)
    schema_version: str = "ntheemba.gateway.inbound.v1"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in {
            "request_id": self.request_id,
            "message_id": self.message_id,
            "channel_instance_id": self.channel_instance_id,
            "provider": self.provider,
            "text": self.text,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.received_at.tzinfo is None:
            raise ValueError("received_at must be timezone-aware")
        object.__setattr__(self, "request_id", self.request_id.strip())
        object.__setattr__(self, "message_id", self.message_id.strip())
        object.__setattr__(self, "channel_instance_id", self.channel_instance_id.strip())
        object.__setattr__(self, "provider", self.provider.strip().casefold())
        object.__setattr__(self, "text", self.text.strip())
        object.__setattr__(self, "recipient_phone", normalize_phone_e164(self.recipient_phone))
        object.__setattr__(self, "customer_phone", normalize_phone_e164(self.customer_phone))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class OutboundGatewayMessage:
    """Exact-channel outgoing message returned to a provider worker."""

    reply_id: str
    request_id: str
    business_id: str
    channel_instance_id: str
    recipient_phone: str
    text: str
    # The authenticated gateway principal that may claim this delivery. Empty
    # is retained only for legacy v1 worker compatibility.
    gateway_id: str = ""
    delivery_target: str = ""
    schema_version: str = "ntheemba.gateway.outbound.v1"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    scope: ChannelScope = ChannelScope.BUSINESS
    platform_role: ChannelRole | None = None

    def __post_init__(self) -> None:
        for name, value in {
            "reply_id": self.reply_id,
            "request_id": self.request_id,
            "channel_instance_id": self.channel_instance_id,
            "text": self.text,
        }.items():
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
        object.__setattr__(self, "recipient_phone", normalize_phone_e164(self.recipient_phone))
        object.__setattr__(self, "gateway_id", self.gateway_id.strip().casefold())
        object.__setattr__(
            self, "delivery_target", self.delivery_target.strip() or self.recipient_phone
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
