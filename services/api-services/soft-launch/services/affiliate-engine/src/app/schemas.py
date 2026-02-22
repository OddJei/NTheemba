from __future__ import annotations

from datetime import datetime
from typing import List
from typing import Any, Dict, Optional
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any


class PaymentCallback(BaseModel):
    event_type: Optional[str] = None
    event_id: Optional[str] = None
    depositId: Optional[str] = None
    payment_id: Optional[str] = None
    id: Optional[str] = None
    business_id: Optional[str] = None
    amount_minor: Optional[int] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None

    # Pydantic v2: prefer `model_config` for configuration
    model_config = ConfigDict(extra="allow", json_schema_extra={
        "example": {
            "event_type": "payment.callback",
            "event_id": "deposit-1234",
            "depositId": "deposit-1234",
            "payment_id": "pay-9876",
            "business_id": "biz-1111",
            "amount": 150.0,
            "currency": "ZMW",
            "status": "payment_success",
            "method": "pawapay",
        }
    })



class AffiliateCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    signed_terms: Optional[bool] = False
    about: Optional[str] = None


class AffiliateOut(BaseModel):
    id: str
    name: str
    phone: Optional[str]
    preferences: Optional[Dict[str, Any]] = None
    signed_terms: bool
    about: Optional[str]
    status: str
    created_at: datetime


class AffiliateLookupOut(BaseModel):
    affiliate_id: str
    location: str

class LinkCreate(BaseModel):
    campaign: Optional[str] = None
    code: Optional[str] = Field(default=None, description="Optional custom code; if omitted, server generates")
    product_id: str
    business_id: str


class LinkOut(BaseModel):
    id: str
    affiliate_id: str
    code: str
    campaign: Optional[str]
    product_id: str
    business_id: str
    created_at: datetime


class AffiliateLinkResolveOut(BaseModel):
    status: Literal["available", "unavailable"]
    reason: Optional[str] = None

    affiliate_code: str
    link_id: Optional[str] = None
    affiliate_id: Optional[str] = None
    business_id: Optional[str] = None
    product_id: Optional[str] = None
    campaign: Optional[str] = None

    token: Optional[str] = None
    token_message: Optional[str] = None
    expires_at: Optional[datetime] = None

    whatsapp_url: Optional[str] = None

    # Optional lightweight preview for static landing page.
    product: Optional[Dict[str, Any]] = None


class TokenResolveRequest(BaseModel):
    token: str
    # Optional phone number supplied by bot (unique buyer identifier)
    buyer_phone: Optional[str] = None
    # Optional session id or chat id from the client/UI
    session_id: Optional[str] = None


class TokenResolveOut(BaseModel):
    product_id: str
    name: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    product_url: Optional[str] = None
    image_url: Optional[str] = None
    affiliate_id: Optional[str] = None
    campaign: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


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


class OrderDeliveredEvent(BaseModel):
    event_id: str
    event_type: str = "order_delivered"
    occurred_at: datetime
    correlation_id: Optional[str]

    order_id: str
    business_id: str
    user_phone: Optional[str] = None
    affiliate_id: Optional[str] = None
    affiliate_code: Optional[str] = None
    order_amount: Optional[float] = None
    amount_zmw: Optional[float] = None
    currency: Optional[str] = None
    cycle_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "event_id": "order-delivered-1234",
            "event_type": "order_delivered",
            "occurred_at": "2026-02-17T12:34:56Z",
            "correlation_id": "corr-abc",
            "order_id": "order-1234",
            "business_id": "biz-1111",
            "user_phone": "260971234567",
            "affiliate_id": "aff-2222",
            "affiliate_code": "AFFCODE123",
            "order_amount": 120.5,
            "amount_zmw": 120.5,
            "currency": "ZMW",
            "cycle_id": "cycle-1",
            "meta": {"note": "delivered via rider"},
        }
    })


class SessionCycleCreatedEvent(BaseModel):
    event_id: str
    event_type: str = "session_cycle_created"
    occurred_at: datetime
    correlation_id: Optional[str]
    producer: str

    affiliate_id: str
    session_id: str
    cycle_id: str
    cycle_state: str

    user_phone: Optional[str] = None
    business_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "event_id": "session-cycle-123",
            "event_type": "session_cycle_created",
            "occurred_at": "2026-02-17T12:00:00Z",
            "correlation_id": "corr-xyz",
            "producer": "bot-session",
            "affiliate_id": "aff-2222",
            "session_id": "sess-abc",
            "cycle_id": "cycle-123",
            "cycle_state": "started",
            "user_phone": "260971234567",
            "business_id": "biz-1111",
            "meta": {"source": "bot"},
        }
    })



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


class TierThreshold(BaseModel):
    tier_name: str
    gmv_min: float
    buyers_min: int
    referrals_min: int
    session_cycles_min: int
    min_metrics_required: int


class TierThresholdUpdate(BaseModel):
    gmv_min: Optional[float] = None
    buyers_min: Optional[int] = None
    referrals_min: Optional[int] = None
    session_cycles_min: Optional[int] = None
    min_metrics_required: Optional[int] = None


class ProjectedPayoutOut(BaseModel):
    """Real-time projected payout for current epoch based on current metrics."""
    affiliate_id: str
    epoch_id: str
    epoch_ends_at: datetime

    # Metrics
    sales_volume: float
    unique_buyers: int
    msme_referrals: int
    clicks: int
    attributions: int
    paid_attributions: int
    session_cycles: int

    # Scoring
    weighted_score: float

    # Tier qualification
    qualified_tiers: list[str]
    effective_tier: Optional[str]
    tier_multiplier: float

    # Payout calculation
    gross_revenue_zmw: float
    pool_pct: float
    pool_amount_zmw: float
    affiliate_share_pct: float
    projected_payout_zmw: float


class PoolStanding(BaseModel):
    affiliate_id: str
    tier_name: Optional[str]
    tier_multiplier: float

    # Tier qualification details (pool policy transparency)
    # - effective_tier: tier used for payout multiplier after qualification/auto-upgrade logic
    # - tier_qualification: structured reasons for eligibility / ineligibility
    effective_tier: Optional[str] = None
    tier_qualification: Optional[Dict[str, Any]] = None

    sales_volume: float
    unique_buyers: int
    msme_referrals: int

    # Clicks is defined as distinct buyer/user phones that clicked within the epoch.
    clicks: int
    attributions: int
    paid_attributions: int
    session_cycles: int

    op_raw: float
    op_final: float
    eligible_for_multiplier: bool
    effective_multiplier: float

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


class MetricSnapshotOut(BaseModel):
    """Snapshot of affiliate metrics at a specific point in time (e.g., epoch close)."""
    
    id: str
    epoch_id: str
    affiliate_id: str

    # Primary weighted metrics (4 metrics)
    sales_volume: float
    unique_buyers: int
    msme_referrals: int
    session_cycles: int

    # Supporting metrics (tracked but not weighted)
    clicks: int
    attributions: int
    paid_attributions: int

    # Scoring result
    weighted_score: float

    # Tier qualification at snapshot time
    qualified_tiers: list[str]  # e.g., ["bronze", "silver"]
    effective_tier: Optional[str]  # Highest qualified tier
    tier_multiplier: float

    # Payout projection
    pool_pct: float
    pool_amount_zmw: float
    affiliate_share_pct: float
    projected_payout_zmw: float

    # Metadata
    meta: Optional[Dict[str, Any]] = None
    
    # Timestamp
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MetricHistoryOut(BaseModel):
    """Historical metrics for an affiliate across epochs."""
    
    affiliate_id: str
    snapshots: list[MetricSnapshotOut]
    total_snapshots: int
    date_range: Optional[tuple[datetime, datetime]] = None

    model_config = ConfigDict(from_attributes=True)


class PayoutStatusCallback(BaseModel):
    """Callback from payment-revenue service with payout status update."""
    
    payout_id: str
    epoch_id: str
    affiliate_id: str
    status: Literal["completed", "failed"]
    amount_zmw: float
    error_message: Optional[str] = None
    completed_at: datetime


class HealthOut(BaseModel):
    status: str


class DebugEpochOut(BaseModel):
    epoch_id: str
    starts_at: datetime
    ends_at: Optional[datetime]
    metrics: List[Dict[str, Any]]
    scores: Dict[str, float]
    details: Dict[str, dict]


class EventEnvelope(BaseModel):
    id: Optional[str] = None
    type: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    occurred_at: Optional[datetime] = None


class MSMEReferralEvent(BaseModel):
    event_id: Optional[str] = None
    event_type: str = "msme_referral"
    occurred_at: Optional[datetime] = None

    deposit_id: str
    affiliate_id: str
    business_id: str

    amount_zmw: Optional[float] = None
    correlation_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(extra="allow", json_schema_extra={
        "example": {
            "event_id": "msme-referral-123",
            "event_type": "msme_referral",
            "deposit_id": "deposit-1234",
            "affiliate_id": "aff-2222",
            "business_id": "biz-1111",
            "amount_zmw": 50.0,
            "correlation_id": "corr-ref",
            "meta": {"note": "first sale for business"},
        }
    })
