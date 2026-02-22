from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field
from typing import List
from pydantic import Extra


# ---- Auth ----


class AuthRegister(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=50)
    password: str = Field(min_length=6, max_length=200)
    role: str = Field(default="default", description="admin|affiliate|msme|staff|default")


class AuthLogin(BaseModel):
    identifier: str = Field(description="username|email|phone")
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    username: str
    email: EmailStr
    phone: Optional[str]
    role: str
    business_id: Optional[str]
    affiliate_id: Optional[str]
    is_active: bool
    signed_terms: bool
    created_at: datetime
    updated_at: datetime


class UserLookupOut(BaseModel):
    user_id: str
    role: str
    business_id: Optional[str]
    affiliate_id: Optional[str]
    is_active: bool


class UserPhoneLookupOut(BaseModel):
    """User details with associated business (if linked)."""
    user: "UserOut"
    business: Optional["BusinessOut"] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    business_id: Optional[str] = None
    affiliate_id: Optional[str] = None
    is_active: Optional[bool] = None


# ---- Business ----


class BusinessOwnerCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    phone: Optional[str] = None
    password: str = Field(min_length=6, max_length=200)


class BusinessRegister(BaseModel):
    owner: Optional[BusinessOwnerCreate] = None
    owner_user_id: Optional[str] = Field(default=None, description="Link an existing user to this business")

    name: str
    location: Optional[str] = None
    category: Optional[str] = None
    logo_url: Optional[str] = None

    affiliate_code: Optional[str] = None
    referred_by_msme_code: Optional[str] = None

    subscription_plan: Optional[str] = None
    # delivery_locations: mapping of town -> metadata (e.g. {"Lusaka": {"price_minor": 2500, "currency":"ZMW"}})
    delivery_locations: Optional[dict[str, dict[str, Any]]] = None
    tags: Optional[list[str]] = None


class BusinessOut(BaseModel):
    id: str
    name: str
    owner_id: str
    location: Optional[str]
    category: Optional[str]
    logo_url: Optional[str]
    affiliate_code: Optional[str]
    referred_by_msme_code: Optional[str]
    subscription_plan: Optional[str]
    subscription_expiry: Optional[datetime]
    delivery_locations: Optional[dict[str, dict[str, Any]]]
    tags: Optional[list[str]]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BusinessRegisterOut(BaseModel):
    business: BusinessOut
    msme_code: str


class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    category: Optional[str] = None
    logo_url: Optional[str] = None
    affiliate_code: Optional[str] = None
    referred_by_msme_code: Optional[str] = None
    delivery_locations: Optional[dict[str, dict[str, Any]]] = None
    tags: Optional[list[str]] = None
    is_active: Optional[bool] = None


class DeliveryLocationsUpdate(BaseModel):
    """Request model for updating delivery locations with per-town metadata.

    Example:
    {
      "Lusaka": {"price_minor": 2500, "currency": "ZMW", "available": True},
      "Ndola": {"price_minor": 3000}
    }
    """
    delivery_locations: dict[str, dict[str, Any]]


class SubscribeRequest(BaseModel):
    plan: str


class SubscribeAndPayRequest(SubscribeRequest):
    # Optional payment details — when provided, msme will initiate a deposit
    # to `payment-revenue` on behalf of the caller.
    amount_minor: Optional[int] = None
    currency: Optional[str] = "ZMW"
    phone_number: Optional[str] = None
    provider: Optional[str] = None
    deposit_id: Optional[str] = None
    billing_interval: Optional[str] = "monthly"


class SubscriptionOut(BaseModel):
    id: str
    business_id: str
    plan: str
    billing_interval: Optional[str] = "monthly"
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    periods_paid: Optional[float] = 0
    paid_through: Optional[datetime] = None
    status: str
    created_at: datetime


class SubscriptionPriceUpdate(BaseModel):
    amount_minor: int
    billing_interval: Optional[str] = "monthly"


class DefaultSubscriptionPriceUpdate(BaseModel):
    amount_minor: int
    billing_interval: Optional[str] = "monthly"
    currency: Optional[str] = "ZMW"
    apply_to_missing: Optional[bool] = False


class DefaultSubscriptionPriceOut(BaseModel):
    billing_interval: str
    amount_minor: int
    currency: str
    updated_at: datetime


class SubscriptionInitiateOut(BaseModel):
    subscription: SubscriptionOut
    payment_request: dict[str, Any]


class BusinessMetadataOut(BaseModel):
    business_id: str
    name: str
    location: Optional[str]
    category: Optional[str]
    tags: Optional[list[str]]
    delivery_locations: Optional[dict[str, Any]]
    is_active: bool


class BusinessEntitlementsOut(BaseModel):
    business_id: str
    plan: str  # free|paid
    subscription_expiry: Optional[datetime] = None
    is_active: bool

    # Feature flags for this plan
    bot_instances_enabled: bool
    affiliate_promo_links_enabled: bool

    # Transaction fee percentage charged by platform (e.g. 0.07 == 7%)
    transaction_fee_pct: float


class BusinessPhoneLookupOut(BaseModel):
    """Business lookup by phone - returns both user and business details."""
    business: BusinessOut
    owner: UserOut


# ---- Events ----


class PaymentSuccessEvent(BaseModel):
    event_id: str
    business_id: str
    plan: str
    paid_until: datetime
    amount: Optional[float] = None
    currency: str = "ZMW"
    source: Optional[str] = None
    billing_interval: Optional[str] = "monthly"


class PaymentFailedEvent(BaseModel):
    event_id: str
    business_id: str
    plan: Optional[str] = None
    reason: Optional[str] = None
    source: Optional[str] = None


class MsmeEventOut(BaseModel):
    event_id: str
    business_id: Optional[str]
    event_type: str
    occurred_at: datetime
    source: Optional[str]
    correlation_id: Optional[str]
    meta: Optional[dict[str, Any]]
    created_at: datetime


# ---- Callbacks / misc requests ----


class PaymentCallback(BaseModel):
    event_type: Optional[str] = None
    event_id: Optional[str] = None
    depositId: Optional[str] = None
    payment_id: Optional[str] = None
    id: Optional[str] = None
    business_id: Optional[str] = None
    amount_minor: Optional[int] = None
    currency: Optional[str] = None
    status: Optional[str] = None

    class Config:
        extra = Extra.allow


class OutboxAckRequest(BaseModel):
    ids: List[str]


# ---- Onboarding (frontend-friendly payloads) ----


class OnboardProfile(BaseModel):
    fullName: str
    email: EmailStr
    phone: Optional[str] = None
    location: Optional[str] = None


class OnboardBusiness(BaseModel):
    businessName: str
    businessType: Optional[str] = None
    description: Optional[str] = None
    yearsInBusiness: Optional[str] = None


class OnboardProduct(BaseModel):
    name: str
    category: Optional[str] = None
    price: str
    initialStock: str


class MSMEOnboardRequest(BaseModel):
    profile: OnboardProfile
    business: OnboardBusiness
    products: List[OnboardProduct]
    signed_terms: bool = Field(default=False, description="Whether the user has signed the platform agreement")


class AffiliatePreferences(BaseModel):
    categories: List[str]
    commissionPreference: Optional[str] = None
    bio: Optional[str] = None


class AffiliateOnboardRequest(BaseModel):
    profile: OnboardProfile
    preferences: AffiliatePreferences
    signed_terms: bool = Field(default=False, description="Whether the user has signed the platform agreement")

