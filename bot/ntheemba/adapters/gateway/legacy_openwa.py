"""Translate the legacy OpenWA payload into the stable Ntheemba gateway envelope."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ntheemba.domain.customers import normalize_phone_e164
from ntheemba.domain.gateway import InboundGatewayMessage


@dataclass(frozen=True, slots=True)
class LegacyOpenWASession:
    """Trusted registration for one legacy OpenWA session."""

    legacy_session_id: str
    channel_instance_id: str
    recipient_phone: str
    provider: str = "openwa"

    def __post_init__(self) -> None:
        if not self.legacy_session_id.strip() or not self.channel_instance_id.strip():
            raise ValueError("legacy and channel session IDs must not be empty")
        object.__setattr__(self, "recipient_phone", normalize_phone_e164(self.recipient_phone))


class LegacyOpenWAEnvelopeAdapter:
    """Do not trust legacy business_id; route through the registered session/channel."""

    def __init__(self, sessions: tuple[LegacyOpenWASession, ...]) -> None:
        self._sessions = {session.legacy_session_id: session for session in sessions}

    def convert_inbound(self, payload: Mapping[str, Any]) -> InboundGatewayMessage:
        legacy_session_id = str(payload.get("session_id", "")).strip()
        session = self._sessions.get(legacy_session_id)
        if session is None:
            raise LookupError(f"unknown legacy OpenWA session {legacy_session_id!r}")
        message_id = str(payload.get("message_id") or payload.get("id") or "").strip()
        if not message_id:
            raise ValueError("legacy payload requires message_id")
        text = str(payload.get("message") or payload.get("body") or "").strip()
        if not text:
            raise ValueError("legacy payload requires message text")
        sender = str(payload.get("from") or payload.get("customer_id") or "").split("@", 1)[0]
        received_at = _parse_timestamp(payload.get("received_at") or payload.get("timestamp"))
        return InboundGatewayMessage(
            request_id=str(payload.get("request_id") or f"LEGACY-{message_id}"),
            message_id=message_id,
            channel_instance_id=session.channel_instance_id,
            provider=session.provider,
            recipient_phone=session.recipient_phone,
            customer_phone=sender,
            text=text,
            received_at=received_at,
            metadata={
                "legacy_session_id": legacy_session_id,
                "legacy_business_id_ignored": str(payload.get("business_id", "")),
            },
        )


def _parse_timestamp(value: object) -> datetime:
    if value is None or value == "":
        return datetime.now(UTC)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000
        return datetime.fromtimestamp(number, tz=UTC)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
