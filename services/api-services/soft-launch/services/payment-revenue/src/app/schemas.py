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
