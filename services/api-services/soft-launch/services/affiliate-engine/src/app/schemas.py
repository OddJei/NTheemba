from __future__ import annotations

from datetime import datetime
from typing import List
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AffiliateCreate(BaseModel):
    name: str
    phone: Optional[str] = None


class AffiliateOut(BaseModel):
    id: str
    name: str
    phone: Optional[str]
    status: str
    created_at: datetime


class LinkCreate(BaseModel):
    campaign: Optional[str] = None
    code: Optional[str] = Field(default=None, description="Optional custom code; if omitted, server generates")


class LinkOut(BaseModel):
    id: str
    affiliate_id: str
    code: str
    campaign: Optional[str]
    created_at: datetime


class ClickCreate(BaseModel):
    event_id: str
    affiliate_code: str
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_phone: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class ClickOut(BaseModel):
    id: str
    link_id: str
    occurred_at: datetime


class AttributionCreate(BaseModel):
    event_id: str
    affiliate_code: Optional[str] = None
    affiliate_id: Optional[str] = None
    click_id: Optional[str] = None

    order_id: str
    business_id: str

    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_phone: Optional[str] = None


class AttributionOut(BaseModel):
    id: str
    affiliate_id: str
    order_id: str
    business_id: str
    status: str
    created_at: datetime


class EarningsBreakdown(BaseModel):
    msme_amount: float
    affiliate_amount: float
    platform_amount: float

    affiliate_id: Optional[str] = None
    affiliate_code: Optional[str] = None


class PaymentSuccessEvent(BaseModel):
    event_id: str
    event_type: str = "payment_success"
    occurred_at: datetime
    correlation_id: str
    producer: str

    payment_id: str
    order_id: Optional[str] = None
    business_id: str
    user_phone: Optional[str] = None

    amount: float
    currency: str

    earnings: EarningsBreakdown


class EarningOut(BaseModel):
    id: str
    affiliate_id: str
    order_id: str
    payment_id: Optional[str]
    amount: float
    currency: str
    status: str
    created_at: datetime


class EarningsSummary(BaseModel):
    affiliate_id: str
    currency: str
    total_amount: float
    pending_amount: float
    ready_amount: float


class EarningsByDay(BaseModel):
    day: str  # YYYY-MM-DD
    amount: float


class AffiliateDashboard(BaseModel):
    affiliate_id: str
    window_days: int

    clicks: int
    attributions: int
    conversions: int
    conversion_rate: float

    total_earnings: float
    pending_earnings: float
    ready_earnings: float
    currency: str

    last_click_at: Optional[datetime] = None
    last_attribution_at: Optional[datetime] = None
    earnings_by_day: List[EarningsByDay] = []


class CommissionSettingsOut(BaseModel):
    pool_pct: float
    epoch_days: int
    weights: Dict[str, float]


class CommissionSettingsUpdate(BaseModel):
    pool_pct: Optional[float] = None
    epoch_days: Optional[int] = None
    weights: Optional[Dict[str, float]] = None


class EpochOut(BaseModel):
    id: str
    starts_at: datetime
    ends_at: Optional[datetime]
    status: str
    gross_revenue_zmw: float
    pool_pct: float
    pool_amount_zmw: float


class EpochSetGrossRevenue(BaseModel):
    gross_revenue_zmw: float


class TierOut(BaseModel):
    name: str
    multiplier: float
    price_zmw: float
    active: bool


class TierAssign(BaseModel):
    tier_name: str
    ends_at: Optional[datetime] = None


class PoolStanding(BaseModel):
    affiliate_id: str
    tier_name: Optional[str]
    tier_multiplier: float

    sales_volume: float
    unique_buyers: int
    msme_referrals: int

    # Clicks is defined as distinct buyer/user phones that clicked within the epoch.
    clicks: int
    attributions: int
    paid_attributions: int

    weighted_score: float
    projected_payout_zmw: float


class PoolStandingsOut(BaseModel):
    epoch: EpochOut
    settings: CommissionSettingsOut
    pool_amount_zmw: float
    standings: list[PoolStanding]


class PoolAllocationOut(BaseModel):
    epoch_id: str
    affiliate_id: str
    tier_name: Optional[str]
    tier_multiplier: float
    metrics: Dict[str, Any]
    weighted_score: float
    payout_zmw: float
    created_at: datetime


class AffiliateEventOut(BaseModel):
    event_id: str
    affiliate_id: Optional[str] = None
    event_type: str
    occurred_at: datetime

    source: Optional[str] = None
    correlation_id: Optional[str] = None

    buyer_phone: Optional[str] = None
    session_id: Optional[str] = None

    order_id: Optional[str] = None
    business_id: Optional[str] = None
    amount_zmw: Optional[float] = None

    meta: Optional[Dict[str, Any]] = None
    created_at: datetime
