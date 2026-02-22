from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CartCreate(BaseModel):
    session_id: str | None = None
    user_phone: str | None = None
    business_id: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"session_id": "sess-123", "user_phone": "+260971000000", "business_id": "biz-1"}
        }
    )

    @model_validator(mode="after")
    def _require_session_or_user(self):
        if not (self.session_id or self.user_phone):
            raise ValueError("either session_id or user_phone is required")
        return self


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
    variant_id: str = Field(...)
    quantity: int = Field(1, ge=1)
    unit_price: float = Field(0.0, ge=0.0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"variant_id": "variant-abc-123", "quantity": 2, "unit_price": 120.5}
        }
    )


class CartItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    cart_id: str
    variant_id: str
    product_name: str | None = None
    media_url: str | None = None
    quantity: int
    reserved_quantity: int
    unit_price: float
    subtotal: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, json_schema_extra={
        "example": {
            "id": "ci-123",
            "cart_id": "cart-1",
            "variant_id": "variant-abc-123",
            "product_name": "Example Product",
            "media_url": "https://example.com/img.jpg",
            "quantity": 2,
            "reserved_quantity": 2,
            "unit_price": 120.5,
            "subtotal": 241.0,
            "created_at": "2026-02-17T12:00:00Z",
        }
    })


class CheckoutOut(BaseModel):
    status: str
    cart_id: str
    total: float

    model_config = ConfigDict(json_schema_extra={
        "example": {"status": "checked_out", "cart_id": "cart-1", "total": 241.0}
    })
