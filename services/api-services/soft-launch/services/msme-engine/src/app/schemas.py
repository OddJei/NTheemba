from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


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
    created_at: datetime
    updated_at: datetime


class UserLookupOut(BaseModel):
    user_id: str
    role: str
    business_id: Optional[str]
    affiliate_id: Optional[str]
    is_active: bool


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
    delivery_locations: Optional[dict[str, Any]] = None
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
    delivery_locations: Optional[dict[str, Any]]
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
    delivery_locations: Optional[dict[str, Any]] = None
    tags: Optional[list[str]] = None
    is_active: Optional[bool] = None


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


class SubscriptionOut(BaseModel):
    id: str
    business_id: str
    plan: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    status: str
    created_at: datetime


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


# ---- Events ----


class PaymentSuccessEvent(BaseModel):
    event_id: str
    business_id: str
    plan: str
    paid_until: datetime
    amount: Optional[float] = None
    currency: str = "ZMW"
    source: Optional[str] = None


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
