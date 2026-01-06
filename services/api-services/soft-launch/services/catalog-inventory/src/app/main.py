from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.db import Base, engine, get_db_session
from src.app.events import add_outbox_event
from src.app.idempotency import idempotent_execute, scope_for
from src.app.models import Category, Inventory, OutboxEvent, Product, ProductVariant
from src.app.schemas import (
    BusinessCatalogOut,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    InventoryOut,
    InventoryUpdate,
    OutboxEventOut,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    VariantCreate,
    VariantOut,
)

app = FastAPI(title="Catalog + Inventory (Soft Launch)")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = correlation_id
    return response


@app.on_event("startup")
async def startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _correlation_id(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


# ---- Health ----


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---- Categories ----


@app.post("/catalog/category", response_model=CategoryOut)
async def category_create(
    payload: CategoryCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        cat = Category(
            business_id=payload.business_id,
            name=payload.name,
            description=payload.description,
            parent_id=payload.parent_id,
            is_active=True,
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        db.add(cat)
        await db.flush()
        add_outbox_event(
            db=db,
            event_type="catalog.category.created",
            business_id=payload.business_id,
            entity_type="category",
            entity_id=cat.id,
            correlation_id=_correlation_id(request),
            meta={"name": payload.name, "parent_id": payload.parent_id},
        )
        await db.commit()
        await db.refresh(cat)
        return 201, cat

    status, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", "/catalog/category"),
        key=x_idempotency_key,
        run=_run,
    )
    response.status_code = int(status)
    return body


@app.get("/catalog/category/{category_id}", response_model=CategoryOut)
async def category_get(category_id: str, db: AsyncSession = Depends(get_db_session)):
    cat = (await db.execute(select(Category).where(Category.id == category_id))).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="category_not_found")
    return cat


@app.get("/catalog/categories", response_model=list[CategoryOut])
async def categories_list(
    business_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(Category)
    if business_id:
        stmt = stmt.where(Category.business_id == business_id)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


@app.put("/catalog/category/{category_id}", response_model=CategoryOut)
async def category_update(
    category_id: str,
    payload: CategoryUpdate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        cat = (await db.execute(select(Category).where(Category.id == category_id))).scalar_one_or_none()
        if not cat:
            raise HTTPException(status_code=404, detail="category_not_found")

        if payload.name is not None:
            cat.name = payload.name
        if payload.description is not None:
            cat.description = payload.description
        if payload.parent_id is not None:
            cat.parent_id = payload.parent_id
        if payload.is_active is not None:
            cat.is_active = bool(payload.is_active)
        cat.updated_at = _utcnow()

        add_outbox_event(
            db=db,
            event_type="catalog.category.updated",
            business_id=cat.business_id,
            entity_type="category",
            entity_id=cat.id,
            correlation_id=_correlation_id(request),
            meta=payload.model_dump(exclude_none=True),
        )

        await db.commit()
        await db.refresh(cat)
        return 200, cat

    status, body = await idempotent_execute(
        db=db,
        scope=scope_for("PUT", "/catalog/category/{id}"),
        key=x_idempotency_key,
        run=_run,
    )
    response.status_code = int(status)
    return body


@app.delete("/catalog/category/{category_id}", response_model=CategoryOut)
async def category_delete(
    category_id: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        cat = (await db.execute(select(Category).where(Category.id == category_id))).scalar_one_or_none()
        if not cat:
            raise HTTPException(status_code=404, detail="category_not_found")

        cat.is_active = False
        cat.updated_at = _utcnow()
        add_outbox_event(
            db=db,
            event_type="catalog.category.deleted",
            business_id=cat.business_id,
            entity_type="category",
            entity_id=cat.id,
            correlation_id=_correlation_id(request),
            meta=None,
        )

        await db.commit()
        await db.refresh(cat)
        return 200, cat

    status, body = await idempotent_execute(
        db=db,
        scope=scope_for("DELETE", "/catalog/category/{id}"),
        key=x_idempotency_key,
        run=_run,
    )
    response.status_code = int(status)
    return body


# ---- Products ----


@app.post("/catalog/product", response_model=ProductOut)
async def product_create(
    payload: ProductCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        prod = Product(
            business_id=payload.business_id,
            category_id=payload.category_id,
            name=payload.name,
            description=payload.description,
            price=payload.price,
            currency=payload.currency,
            image_url=payload.image_url,
            tags=payload.tags,
            is_active=True,
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        db.add(prod)
        await db.flush()

        add_outbox_event(
            db=db,
            event_type="catalog.product.created",
            business_id=payload.business_id,
            entity_type="product",
            entity_id=prod.id,
            correlation_id=_correlation_id(request),
            meta={"name": payload.name, "category_id": payload.category_id},
        )

        await db.commit()
        await db.refresh(prod)
        return 201, prod

    status, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", "/catalog/product"),
        key=x_idempotency_key,
        run=_run,
    )
    response.status_code = int(status)
    return body


@app.get("/catalog/product/{product_id}", response_model=ProductOut)
async def product_get(product_id: str, db: AsyncSession = Depends(get_db_session)):
    prod = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="product_not_found")
    return prod


@app.put("/catalog/product/{product_id}", response_model=ProductOut)
async def product_update(
    product_id: str,
    payload: ProductUpdate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        prod = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
        if not prod:
            raise HTTPException(status_code=404, detail="product_not_found")

        for field_name, value in payload.model_dump(exclude_none=True).items():
            setattr(prod, field_name, value)
        prod.updated_at = _utcnow()

        add_outbox_event(
            db=db,
            event_type="catalog.product.updated",
            business_id=prod.business_id,
            entity_type="product",
            entity_id=prod.id,
            correlation_id=_correlation_id(request),
            meta=payload.model_dump(exclude_none=True),
        )

        await db.commit()
        await db.refresh(prod)
        return 200, prod

    status, body = await idempotent_execute(
        db=db,
        scope=scope_for("PUT", "/catalog/product/{id}"),
        key=x_idempotency_key,
        run=_run,
    )
    response.status_code = int(status)
    return body


@app.delete("/catalog/product/{product_id}", response_model=ProductOut)
async def product_delete(
    product_id: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        prod = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
        if not prod:
            raise HTTPException(status_code=404, detail="product_not_found")

        prod.is_active = False
        prod.updated_at = _utcnow()

        add_outbox_event(
            db=db,
            event_type="catalog.product.deleted",
            business_id=prod.business_id,
            entity_type="product",
            entity_id=prod.id,
            correlation_id=_correlation_id(request),
            meta=None,
        )

        await db.commit()
        await db.refresh(prod)
        return 200, prod

    status, body = await idempotent_execute(
        db=db,
        scope=scope_for("DELETE", "/catalog/product/{id}"),
        key=x_idempotency_key,
        run=_run,
    )
    response.status_code = int(status)
    return body


@app.post("/catalog/product/{product_id}/variant", response_model=VariantOut)
async def variant_add(
    product_id: str,
    payload: VariantCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        prod = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
        if not prod:
            raise HTTPException(status_code=404, detail="product_not_found")

        variant = ProductVariant(
            product_id=product_id,
            name=payload.name,
            sku=payload.sku,
            price_override=payload.price_override,
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        db.add(variant)

        await db.flush()

        # Ensure an inventory row exists for this variant
        inv = Inventory(
            variant_id=variant.id,
            stock_level=0,
            reserved=0,
            threshold=0,
            updated_at=_utcnow(),
        )
        db.add(inv)

        add_outbox_event(
            db=db,
            event_type="catalog.variant.created",
            business_id=prod.business_id,
            entity_type="variant",
            entity_id=variant.id,
            correlation_id=_correlation_id(request),
            meta={"product_id": product_id, "sku": payload.sku, "name": payload.name},
        )

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=409, detail="variant_sku_already_exists")

        await db.refresh(variant)
        return 201, variant

    status, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", "/catalog/product/{id}/variant"),
        key=x_idempotency_key,
        run=_run,
    )
    response.status_code = int(status)
    return body


@app.get("/catalog/business/{business_id}", response_model=BusinessCatalogOut)
async def catalog_by_business(business_id: str, db: AsyncSession = Depends(get_db_session)):
    products = (await db.execute(select(Product).where(Product.business_id == business_id))).scalars().all()
    product_ids = [p.id for p in products]

    variants: list[ProductVariant] = []
    if product_ids:
        variants = (
            await db.execute(select(ProductVariant).where(ProductVariant.product_id.in_(product_ids)))
        ).scalars().all()

    return BusinessCatalogOut(business_id=business_id, products=list(products), variants=list(variants))


@app.post("/catalog/reindex/{business_id}")
async def catalog_reindex(
    business_id: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        add_outbox_event(
            db=db,
            event_type="catalog.reindex.requested",
            business_id=business_id,
            entity_type="business",
            entity_id=business_id,
            correlation_id=_correlation_id(request),
            meta=None,
        )
        await db.commit()
        return 202, {"status": "queued", "business_id": business_id}

    status, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", "/catalog/reindex/{business_id}"),
        key=x_idempotency_key,
        run=_run,
    )
    response.status_code = int(status)
    return body


# ---- Inventory ----


@app.post("/inventory/update", response_model=InventoryOut)
async def inventory_update(
    payload: InventoryUpdate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        inv = (await db.execute(select(Inventory).where(Inventory.variant_id == payload.variant_id))).scalar_one_or_none()
        old_stock = int(inv.stock_level) if inv else 0

        if not inv:
            inv = Inventory(
                variant_id=payload.variant_id,
                stock_level=0,
                reserved=0,
                threshold=0,
                updated_at=_utcnow(),
            )
            db.add(inv)
            await db.flush()

        inv.stock_level = max(0, int(inv.stock_level) + int(payload.delta))

        reserved_delta = int(payload.reserved_delta or 0)
        new_reserved = max(0, int(inv.reserved) + reserved_delta)
        inv.reserved = min(inv.stock_level, new_reserved)

        if payload.threshold is not None:
            inv.threshold = int(payload.threshold)

        inv.updated_at = _utcnow()

        meta: dict[str, Any] = {
            "variant_id": payload.variant_id,
            "delta": int(payload.delta),
            "reserved_delta": int(payload.reserved_delta or 0),
            "stock_level": int(inv.stock_level),
            "reserved": int(inv.reserved),
            "threshold": int(inv.threshold),
        }
        if payload.reason is not None:
            meta["reason"] = payload.reason
        if payload.meta is not None:
            meta["meta"] = payload.meta

        add_outbox_event(
            db=db,
            event_type="inventory.updated",
            entity_type="variant",
            entity_id=payload.variant_id,
            correlation_id=_correlation_id(request),
            meta=meta,
        )

        if int(inv.stock_level) == 0:
            add_outbox_event(
                db=db,
                event_type="inventory.out_of_stock",
                entity_type="variant",
                entity_id=payload.variant_id,
                correlation_id=_correlation_id(request),
                meta={"variant_id": payload.variant_id},
            )
        elif old_stock == 0 and int(inv.stock_level) > 0:
            add_outbox_event(
                db=db,
                event_type="inventory.restocked",
                entity_type="variant",
                entity_id=payload.variant_id,
                correlation_id=_correlation_id(request),
                meta={"variant_id": payload.variant_id, "stock_level": int(inv.stock_level)},
            )

        if int(inv.threshold) > 0 and int(inv.stock_level) <= int(inv.threshold):
            add_outbox_event(
                db=db,
                event_type="inventory.low_stock",
                entity_type="variant",
                entity_id=payload.variant_id,
                correlation_id=_correlation_id(request),
                meta={
                    "variant_id": payload.variant_id,
                    "stock_level": int(inv.stock_level),
                    "threshold": int(inv.threshold),
                },
            )

        await db.commit()
        await db.refresh(inv)
        return 200, inv

    status, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", "/inventory/update"),
        key=x_idempotency_key,
        run=_run,
    )
    response.status_code = int(status)
    return body


@app.get("/inventory/{variant_id}", response_model=InventoryOut)
async def inventory_get(variant_id: str, db: AsyncSession = Depends(get_db_session)):
    inv = (await db.execute(select(Inventory).where(Inventory.variant_id == variant_id))).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="inventory_not_found")
    return inv


# ---- Outbox events (debug) ----


@app.get("/events", response_model=list[OutboxEventOut])
async def events_list(limit: int = 100, db: AsyncSession = Depends(get_db_session)):
    stmt = select(OutboxEvent).order_by(OutboxEvent.created_at.desc()).limit(int(limit))
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)
