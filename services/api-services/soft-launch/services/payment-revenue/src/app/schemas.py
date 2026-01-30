from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class OrmBaseModel(BaseModel):
    model_config = {"from_attributes": True, "populate_by_name": True}


class PaymentSuccessIn(OrmBaseModel):
    payment_id: str
    order_id: str
    business_id: str

    # Use integer minor units for real-money correctness.
    amount_minor: int = Field(ge=0)
    currency: str = "ZMW"

    user_phone: Optional[str] = None
    occurred_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubscriptionPaymentSuccessIn(OrmBaseModel):
    payment_id: str
    business_id: str

    plan: str
    paid_until: datetime

    amount_minor: int = Field(ge=0)
    currency: str = "ZMW"

    occurred_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SettlementOut(OrmBaseModel):
    id: str
    order_id: str
    payment_id: str
    business_id: str
    currency: str
    amount_minor: int

    fee_bps: int
    platform_fee_minor: int
    affiliate_commission_minor: int
    msme_net_minor: int

    status: str
    dispatched: bool
    meta: dict[str, Any] = Field(alias="metadata")
    created_at: datetime
    updated_at: datetime


class PayoutOut(OrmBaseModel):
    id: str
    order_id: str
    payment_id: str
    business_id: str

    payee_type: str
    payee_id: Optional[str] = None

    currency: str
    amount_minor: int

    status: str
    meta: dict[str, Any] = Field(alias="metadata")
    created_at: datetime
    updated_at: datetime


class SubscriptionPaymentOut(OrmBaseModel):
    id: str
    payment_id: str
    business_id: str
    plan: str
    paid_until: datetime
    currency: str
    amount_minor: int
    status: str
    dispatched: bool
    meta: dict[str, Any] = Field(alias="metadata")
    created_at: datetime
    updated_at: datetime


class StatusOut(OrmBaseModel):
    status: str


class RefundRequestIn(OrmBaseModel):
    order_id: str
    reason: Optional[str] = None


class RefundOut(OrmBaseModel):
    status: str
    order_id: str
    business_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


# -----------------
# pawaPay (Zambia)
# -----------------


class PawaPayDepositInitiateIn(OrmBaseModel):
    # Optional so callers can retry with the same ID.
    deposit_id: Optional[str] = Field(default=None, alias="depositId")

    order_id: Optional[str] = None
    business_id: Optional[str] = None

    amount_minor: int = Field(ge=0)
    currency: str = "ZMW"

    phone_number: str = Field(alias="phoneNumber")
    provider: Optional[str] = None  # Auto-inferred from phone if not provided

    metadata: dict[str, Any] = Field(default_factory=dict)


class PawaPayPayoutInitiateIn(OrmBaseModel):
    payout_id: Optional[str] = Field(default=None, alias="payoutId")

    order_id: Optional[str] = None
    business_id: Optional[str] = None

    amount_minor: int = Field(ge=0)
    currency: str = "ZMW"

    phone_number: str = Field(alias="phoneNumber")
    provider: Optional[str] = None  # Auto-inferred from phone if not provided

    metadata: dict[str, Any] = Field(default_factory=dict)


class PawaPayRefundInitiateIn(OrmBaseModel):
    refund_id: Optional[str] = Field(default=None, alias="refundId")
    deposit_id: str = Field(alias="depositId")

    # Optional for partial refunds.
    amount_minor: Optional[int] = Field(default=None, ge=0)
    currency: Optional[str] = None

    order_id: Optional[str] = None
    business_id: Optional[str] = None

    metadata: dict[str, Any] = Field(default_factory=dict)


class PawaPayTxnOut(OrmBaseModel):
    # Works for deposit/payout/refund.
    external_id: str
    status: str
    amount_minor: int
    currency: str
    provider: Optional[str] = None
    phone_number: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
