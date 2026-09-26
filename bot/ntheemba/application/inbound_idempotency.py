"""Generic inbound idempotency across business and platform channel scopes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from ntheemba.domain.gateway import InboundGatewayMessage
from ntheemba.ports.idempotency import IdempotencyRecord, IdempotencyStore


@dataclass(frozen=True, slots=True)
class InboundClaim:
    """One live claim over a provider/channel/message tuple."""

    key: str
    owner_token: str
    duplicate: bool = False
    existing: IdempotencyRecord | None = None


class InboundMessageIdempotency:
    """Protect the generic inbound boundary from duplicate provider deliveries."""

    def __init__(self, store: IdempotencyStore, *, ttl: timedelta) -> None:
        if ttl <= timedelta(0):
            raise ValueError("ttl must be greater than zero")
        self.store = store
        self.ttl = ttl

    async def claim(
        self,
        message: InboundGatewayMessage,
        *,
        owner_token: str,
    ) -> InboundClaim:
        if not owner_token.strip():
            raise ValueError("owner_token must not be empty")
        key = self.key_for(message)
        claimed = await self.store.claim(key, owner_token=owner_token, ttl=self.ttl)
        if claimed:
            return InboundClaim(key=key, owner_token=owner_token)
        return InboundClaim(
            key=key,
            owner_token=owner_token,
            duplicate=True,
            existing=await self.store.get(key),
        )

    async def complete(
        self,
        claim: InboundClaim,
        *,
        status: str,
        request_id: str,
    ) -> bool:
        if claim.duplicate:
            return False
        return await self.store.complete(
            claim.key,
            owner_token=claim.owner_token,
            result={"status": status, "request_id": request_id},
            ttl=self.ttl,
        )

    async def fail(
        self,
        claim: InboundClaim,
        *,
        reason: str,
        request_id: str,
    ) -> bool:
        if claim.duplicate:
            return False
        return await self.store.fail(
            claim.key,
            owner_token=claim.owner_token,
            result={"status": "failed", "reason": reason, "request_id": request_id},
            ttl=self.ttl,
        )

    async def release(self, claim: InboundClaim) -> bool:
        if claim.duplicate:
            return False
        return await self.store.release(claim.key, owner_token=claim.owner_token)

    @staticmethod
    def key_for(message: InboundGatewayMessage) -> str:
        """Use exact provider/channel identity without putting phone numbers into storage keys."""

        provider = message.provider.strip().lower()
        channel = message.channel_instance_id.strip()
        message_id = message.message_id.strip()
        return f"gateway-inbound:{provider}:{channel}:{message_id}"
