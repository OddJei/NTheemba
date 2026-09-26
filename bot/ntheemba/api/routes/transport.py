"""Transport-neutral, gateway-authenticated v2 ingress.

Gateways normalise their own provider payloads at this boundary.  Business,
shop, capability, and platform scope are deliberately absent from the wire
contract and are resolved only from Ntheemba's durable channel binding.
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from ntheemba.config import Settings
from ntheemba.domain.gateway import InboundGatewayMessage
from ntheemba.ports.idempotency import IdempotencyStatus

router = APIRouter(prefix="/transport", tags=["transport"])


class TransportInboundRequest(BaseModel):
    """Text-only v2 envelope shared by every independently deployed gateway."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    message_id: str = Field(alias="messageId", min_length=1, max_length=300)
    external_session_id: str = Field(alias="externalSessionId", min_length=1, max_length=200)
    recipient_identifier: str = Field(alias="recipientIdentifier", min_length=8, max_length=200)
    sender_identifier: str = Field(alias="senderIdentifier", min_length=8, max_length=200)
    text: str = Field(min_length=1, max_length=4_000)
    occurred_at: datetime = Field(alias="occurredAt")
    correlation_id: str = Field(alias="correlationId", min_length=1, max_length=200)
    metadata: dict[str, str] = Field(default_factory=dict)


class TransportAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "accepted"
    delivery_id: str
    correlation_id: str
    duplicate: bool = False


class TransportOutboundClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    consumer_id: str = Field(alias="consumerId", min_length=1, max_length=200)


class TransportOutboundDelivery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    delivery_id: str = Field(alias="deliveryId")
    message_id: str = Field(alias="messageId")
    correlation_id: str = Field(alias="correlationId")
    delivery_target: str = Field(alias="deliveryTarget")
    text: str
    idempotency_key: str = Field(alias="idempotencyKey")
    attempt: int


class TransportOutboundClaimResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery: TransportOutboundDelivery | None = None


class TransportOutboundAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    consumer_id: str = Field(alias="consumerId", min_length=1, max_length=200)
    outcome: str = Field(pattern="^(sent|failed)$")
    failure_code: str = Field(default="", alias="failureCode", max_length=120)


def _gateway_id(settings: Settings, authorization: str | None, supplied: str | None) -> str:
    gateway_id = (supplied or "").strip().casefold()
    expected = settings.transport_gateway_tokens.get(gateway_id)
    if (
        not gateway_id
        or expected is None
        or authorization is None
        or not authorization.startswith("Bearer ")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid gateway credentials."
        )
    if not hmac.compare_digest(authorization.removeprefix("Bearer ").strip(), expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid gateway credentials."
        )
    return gateway_id


def _validate_freshness(occurred_at: datetime, window_seconds: int) -> None:
    if occurred_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="occurredAt must include a timezone.")
    if abs(datetime.now(UTC) - occurred_at.astimezone(UTC)) > timedelta(seconds=window_seconds):
        raise HTTPException(
            status_code=409, detail="Transport message is outside the replay window."
        )


@router.post(
    "/inbound",
    response_model=TransportAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_transport_inbound(
    payload: TransportInboundRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    gateway_id_header: str | None = Header(default=None, alias="X-Ntheemba-Gateway-ID"),
) -> TransportAcceptedResponse:
    settings: Settings = request.app.state.settings
    gateway_id = _gateway_id(settings, authorization, gateway_id_header)
    _validate_freshness(payload.occurred_at, settings.transport_replay_window_seconds)
    metadata_oversized = any(
        len(key) > 80 or len(value) > 500 for key, value in payload.metadata.items()
    )
    if len(payload.metadata) > 20 or metadata_oversized:
        raise HTTPException(status_code=422, detail="Transport metadata exceeds the safe limit.")

    storage = request.app.state.storage_runtime
    channel = await storage.business_registry.get_channel_by_identity(
        gateway_id, payload.external_session_id, payload.recipient_identifier
    )
    if channel is None or not channel.enabled:
        raise HTTPException(
            status_code=404, detail="No enabled channel matches this transport identity."
        )

    key = (
        f"transport-inbound:{gateway_id}:{channel.channel_instance_id}:"
        f"{payload.message_id.strip()}"
    )
    owner = f"transport-api:{uuid4()}"
    claimed = await storage.idempotency.claim(
        key, owner_token=owner, ttl=timedelta(seconds=settings.deduplication_ttl_seconds)
    )
    if not claimed:
        previous = await storage.idempotency.get(key)
        if previous is not None and previous.status is IdempotencyStatus.COMPLETED:
            return TransportAcceptedResponse(
                delivery_id=str(previous.result.get("delivery_id", "")),
                correlation_id=payload.correlation_id,
                duplicate=True,
            )
        raise HTTPException(status_code=409, detail="Transport message is already being accepted.")

    try:
        # The v2 payload does not carry Ntheemba's internal channel identifier;
        # it is obtained only from the exact registered binding above.
        message = InboundGatewayMessage(
            request_id=payload.correlation_id,
            message_id=payload.message_id,
            channel_instance_id=channel.channel_instance_id,
            provider=gateway_id,
            recipient_phone=payload.recipient_identifier,
            customer_phone=payload.sender_identifier,
            text=payload.text,
            received_at=payload.occurred_at,
            schema_version="ntheemba.transport.inbound.v2",
            metadata={**payload.metadata, "gateway_id": gateway_id},
        )
        delivery_id = await storage.gateway_queue.enqueue_inbound(message)
        await storage.idempotency.complete(
            key, owner_token=owner, result={"delivery_id": delivery_id},
            ttl=timedelta(seconds=settings.deduplication_ttl_seconds),
        )
    except Exception:
        await storage.idempotency.release(key, owner_token=owner)
        raise
    return TransportAcceptedResponse(delivery_id=delivery_id, correlation_id=payload.correlation_id)


@router.post("/outbound/claim", response_model=TransportOutboundClaimResponse)
async def claim_transport_outbound(
    payload: TransportOutboundClaimRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    gateway_id_header: str | None = Header(default=None, alias="X-Ntheemba-Gateway-ID"),
) -> TransportOutboundClaimResponse:
    gateway_id = _gateway_id(request.app.state.settings, authorization, gateway_id_header)
    claimed = await request.app.state.storage_runtime.gateway_queue.claim_outbound(
        payload.consumer_id, gateway_id
    )
    if claimed is None:
        return TransportOutboundClaimResponse()
    message = claimed.message
    return TransportOutboundClaimResponse(
        delivery=TransportOutboundDelivery(
            deliveryId=claimed.delivery_id,
            messageId=message.reply_id,
            correlationId=message.request_id,
            deliveryTarget=message.delivery_target,
            text=message.text,
            idempotencyKey=str(message.metadata.get("idempotency_key") or message.reply_id),
            attempt=claimed.attempt,
        )
    )


@router.post("/outbound/{delivery_id}/ack", status_code=status.HTTP_204_NO_CONTENT)
async def acknowledge_transport_outbound(
    delivery_id: str,
    payload: TransportOutboundAckRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    gateway_id_header: str | None = Header(default=None, alias="X-Ntheemba-Gateway-ID"),
) -> None:
    gateway_id = _gateway_id(request.app.state.settings, authorization, gateway_id_header)
    queue = request.app.state.storage_runtime.gateway_queue
    try:
        if payload.outcome == "sent":
            await queue.acknowledge_outbound(delivery_id, payload.consumer_id, gateway_id)
        else:
            await queue.dead_letter_outbound(
                delivery_id,
                payload.consumer_id,
                payload.failure_code or "gateway_reported_failure",
                gateway_id,
            )
    except (LookupError, PermissionError) as error:
        raise HTTPException(status_code=404, detail="Outbound delivery is unavailable.") from error
