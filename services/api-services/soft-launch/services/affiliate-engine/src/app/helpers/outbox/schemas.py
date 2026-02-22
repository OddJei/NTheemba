from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class NotificationPayload(BaseModel):
    channel: str
    user_id: Optional[str] = None
    business_id: Optional[str] = None
    template: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)


class EmailPayload(BaseModel):
    to: str
    subject: str
    message: Optional[str] = None
    html: Optional[str] = None


class WhatsAppPayload(BaseModel):
    to: str
    text: str
    from_: Optional[str] = Field(default=None, alias="from")


class DepositRequested(BaseModel):
    subscription_id: Optional[str] = None
    business_id: str
    amount_minor: int
    currency: str = "ZMW"
    phoneNumber: Optional[str] = None
    paymentType: str = "subscription"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PawapayDepositInitiator(BaseModel):
    event_id: str
    event_type: str
    occurred_at: str
    correlation_id: Optional[str] = None
    producer: str
    payment_id: Optional[str] = None
    depositId: Optional[str] = None
    amount_minor: int
    amount: float
    order_id: Optional[str] = None
    business_id: Optional[str] = None
    currency: str
    provider: Optional[str] = None
    provider_transaction_id: Optional[str] = None
    platform_fee_minor: Optional[int] = 0
    fee_bps: Optional[int] = None
    payment_type: Optional[str] = None
    msme_net_minor: Optional[int] = 0
    meta: dict[str, Any] = Field(default_factory=dict)
    # Failure fields
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    response: Optional[Any] = None

    model_config = {"extra": "allow"}
