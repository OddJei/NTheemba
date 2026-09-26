"""Authenticated provider-neutral gateway ingestion boundary."""

from __future__ import annotations

import hmac
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from ntheemba.config import Settings
from ntheemba.domain.gateway import InboundGatewayMessage
from ntheemba.infrastructure.storage import StorageRuntime

router = APIRouter(prefix="/gateway", tags=["gateway"])


class GatewayInboundRequest(BaseModel):
    """Stable HTTP representation of the inbound gateway envelope."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    request_id: str = Field(alias="requestId", min_length=1, max_length=200)
    message_id: str = Field(alias="messageId", min_length=1, max_length=300)
    channel_instance_id: str = Field(
        alias="channelInstanceId", min_length=1, max_length=200
    )
    provider: str = Field(min_length=1, max_length=100)
    recipient_phone: str = Field(alias="recipientPhone", min_length=8, max_length=30)
    customer_phone: str = Field(alias="customerPhone", min_length=8, max_length=30)
    text: str = Field(min_length=1, max_length=4000)
    received_at: datetime = Field(alias="receivedAt")
    schema_version: str = Field(
        default="ntheemba.gateway.inbound.v1",
        alias="schemaVersion",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class GatewayAcceptedResponse(BaseModel):
    """Queue acceptance response; processing occurs through the worker."""

    model_config = ConfigDict(extra="forbid")

    status: str = "accepted"
    delivery_id: str
    request_id: str


def _authorized(settings: Settings, authorization: str | None) -> bool:
    secret = settings.gateway_shared_secret
    if secret is None:
        return False
    if authorization is None or not authorization.startswith("Bearer "):
        return False
    supplied = authorization.removeprefix("Bearer ").strip()
    return hmac.compare_digest(supplied, secret.get_secret_value())


@router.post(
    "/inbound",
    response_model=GatewayAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_inbound_gateway_message(
    payload: GatewayInboundRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> GatewayAcceptedResponse:
    settings: Settings = request.app.state.settings
    if settings.gateway_shared_secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway ingestion is not configured.",
        )
    if not _authorized(settings, authorization):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid gateway credentials.",
        )
    storage: StorageRuntime = request.app.state.storage_runtime
    message = InboundGatewayMessage(
        request_id=payload.request_id,
        message_id=payload.message_id,
        channel_instance_id=payload.channel_instance_id,
        provider=payload.provider,
        recipient_phone=payload.recipient_phone,
        customer_phone=payload.customer_phone,
        text=payload.text,
        received_at=payload.received_at,
        schema_version=payload.schema_version,
        metadata=payload.metadata,
    )
    delivery_id = await storage.gateway_queue.enqueue_inbound(message)
    return GatewayAcceptedResponse(
        delivery_id=delivery_id,
        request_id=payload.request_id,
    )
