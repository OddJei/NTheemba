from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class CartCreate(BaseModel):
    session_id: str | None = None
    user_phone: str | None = None
    business_id: str | None = None


class CartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str | None
    user_phone: str | None
    business_id: str | None
    status: str
    meta: dict | None
    created_at: datetime
    updated_at: datetime


class CartItemCreate(BaseModel):
    variant_id: str
    quantity: int = 1
    unit_price: float = 0.0


class CartItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    cart_id: str
    variant_id: str
    quantity: int
    unit_price: float
    subtotal: float
    created_at: datetime


class CheckoutOut(BaseModel):
    status: str
    cart_id: str
    total: float
