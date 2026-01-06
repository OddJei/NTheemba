from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---- Categories ----


class CategoryCreate(BaseModel):
    business_id: str | None = None
    name: str
    description: str | None = None
    parent_id: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    parent_id: str | None = None
    is_active: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str | None
    name: str
    description: str | None
    parent_id: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---- Products ----


class ProductCreate(BaseModel):
    business_id: str
    category_id: str | None = None
    name: str
    description: str | None = None
    price: float
    currency: str = "ZMW"
    image_url: str | None = None
    tags: list[str] | None = None


class ProductUpdate(BaseModel):
    category_id: str | None = None
    name: str | None = None
    description: str | None = None
    price: float | None = None
    currency: str | None = None
    image_url: str | None = None
    tags: list[str] | None = None
    is_active: bool | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    category_id: str | None
    name: str
    description: str | None
    price: float
    currency: str
    image_url: str | None
    tags: list[str] | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---- Variants ----


class VariantCreate(BaseModel):
    name: str
    sku: str
    price_override: float | None = None


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    name: str
    sku: str
    price_override: float | None
    created_at: datetime
    updated_at: datetime


class BusinessCatalogOut(BaseModel):
    business_id: str
    products: list[ProductOut]
    variants: list[VariantOut]


# ---- Inventory ----


class InventoryUpdate(BaseModel):
    variant_id: str
    delta: int = Field(..., description="Signed stock adjustment (+/-).")
    reserved_delta: int | None = Field(default=0, description="Signed reserved adjustment (+/-).")
    threshold: int | None = None
    reason: str | None = None
    meta: dict[str, Any] | None = None


class InventoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    variant_id: str
    stock_level: int
    reserved: int
    threshold: int
    updated_at: datetime


# ---- Outbox Events ----


class OutboxEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    business_id: str | None
    entity_type: str | None
    entity_id: str | None
    source: str | None
    correlation_id: str | None
    meta: dict[str, Any] | None
    created_at: datetime
