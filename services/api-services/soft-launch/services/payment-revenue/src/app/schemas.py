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


class GrossRevenueOut(OrmBaseModel):
    """Gross revenue calculation response."""
    gross_revenue_zmw: float
    subscription_revenue_zmw: float
    platform_fee_revenue_zmw: float
    transaction_count: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    epoch_id: Optional[str] = None
    calculated_at: datetime


class PlatformBalanceOut(OrmBaseModel):
    """Current platform balance (total money held)."""
    platform_balance_zmw: float
    total_inflows_zmw: float
    total_outflows_zmw: float
    calculated_at: datetime


class MSMEPayoutInitiateIn(OrmBaseModel):
    """Request to initiate MSME payout for a delivered order."""
    order_id: str
    business_id: str
    msme_phone: str
    order_amount_minor: int = Field(ge=0)
    currency: str = "ZMW"
    metadata: dict[str, Any] = Field(default_factory=dict)


class MSMEPayoutOut(OrmBaseModel):
    """MSME payout record response."""
    id: str
    payout_id: str
    order_id: str
    business_id: str
    msme_phone: str
    provider: Optional[str]
    amount_minor: int
    platform_fee_minor: int
    currency: str
    status: str
    failure_code: Optional[str]
    failure_message: Optional[str]
    initiated_at: datetime
    completed_at: Optional[datetime]


class PayoutRequestIn(OrmBaseModel):
    """Individual payout request in a batch."""
    affiliate_id: str
    amount_zmw: float
    currency: str = "ZMW"
    phone_number: Optional[str] = None


class PayoutBatchRequestIn(OrmBaseModel):
    """Batch payout request from affiliate-engine."""
    epoch_id: str
    payouts: list[PayoutRequestIn]
    callback_url: str


class AffiliatePayoutOut(OrmBaseModel):
    """Response for individual affiliate payout."""
    affiliate_id: str
    payout_id: str
    amount_zmw: float
    currency: str
    status: str  # accepted, processing, completed, failed
    initiated_at: datetime


class PayoutBatchResponseOut(OrmBaseModel):
    """Response for batch payout request."""
    batch_id: str
    epoch_id: str
    total_payouts: int
    total_amount_zmw: float
    payouts: list[AffiliatePayoutOut]
    status: str  # accepted, processing
    initiated_at: datetime
