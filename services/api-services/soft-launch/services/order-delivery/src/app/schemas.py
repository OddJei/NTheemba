from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class OrmBaseModel(BaseModel):
    model_config = {"from_attributes": True, "populate_by_name": True}


DeliveryMethod = Literal["pickup", "deliver_to_customer"]
OrderStatus = Literal["pending_payment", "paid", "delivered"]
DeliveryStatus = Literal["pending", "code_sent", "confirmed"]


class OrderCreate(OrmBaseModel):
    session_id: Optional[str] = None
    user_phone: str
    user_id: Optional[str] = None
    business_id: str
    delivery_method: DeliveryMethod = "pickup"
    total_amount: int = Field(ge=0)
    currency: str = "ZAR"
    meta: dict[str, Any] = Field(default_factory=dict, alias="metadata")


class OrderOut(OrmBaseModel):
    id: str
    session_id: Optional[str]
    user_phone: str
    user_id: Optional[str]
    business_id: str
    status: str
    delivery_method: str
    total_amount: int
    currency: str
    meta: dict[str, Any] = Field(alias="metadata")
    created_at: datetime
    updated_at: datetime


class DeliveryOut(OrmBaseModel):
    id: str
    order_id: str
    user_phone: str
    user_id: Optional[str]
    business_id: str
    delivery_method: str
    status: str
    confirmed_by: Optional[str]
    meta: dict[str, Any] = Field(alias="metadata")
    created_at: datetime
    updated_at: datetime


class DeliveryInitiateOut(OrmBaseModel):
    delivery: DeliveryOut
    delivery_code: str


class DeliveryConfirmIn(OrmBaseModel):
    delivery_code: str
    confirmed_by: Optional[str] = None


class StatusOut(OrmBaseModel):
    status: str


class PaymentInitiateIn(OrmBaseModel):
    phone_number: str = Field(alias="phoneNumber")
    provider: Optional[str] = None
    currency: str = "ZMW"


class PaymentStatusOut(OrmBaseModel):
    external_id: str
    status: str
    amount_minor: int
    currency: str
    provider: str
    phone_number: str
    meta: dict[str, Any] = Field(default_factory=dict)


class OrderSummary(OrmBaseModel):
    id: str
    status: str
    total_amount: int
    currency: str
    meta: dict[str, Any] = Field(default_factory=dict)


# Mapping of subject -> list of order summaries
class CustomerSummary(OrmBaseModel):
    user_phone: str
    user_id: Optional[str] = None


class DeliverySummary(OrmBaseModel):
    delivery_id: Optional[str] = None
    status: Optional[str] = None
    # intentionally exclude delivery_code for security


class PendingPage(OrmBaseModel):
    items: list[OrderSummary]
    total: int
    offset: int
    limit: int


class PendingGroup(OrmBaseModel):
    pending_payment: PendingPage
    pending_delivery: PendingPage


PendingOrdersOut = dict[str, PendingGroup]
 

class DenyRequest(OrmBaseModel):
    reason: Optional[str] = None
    initiate_refund: bool = True
