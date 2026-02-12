from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
import httpx
import asyncio
import os

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, Response, File, UploadFile
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.db import Base, engine, get_db_session
from src.app.config import get_notification_base_url, get_notification_timeout_seconds, skip_msme_validation
from src.app.events import add_outbox_event
from src.app.idempotency import idempotent_execute, scope_for
from src.app.models import Category, Inventory, OutboxEvent, Product, ProductVariant
from src.app import audit_client
from src.app import security
from src.app.schemas import (
    BusinessCatalogOut,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    InventoryOut,
    InventoryUpdate,
    MediaUploadBatch,
    OutboxEventOut,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    VariantCreate,
    VariantOut,
)
from src.app.uploads import generate_presigned_put_url, generate_presigned_get_url, process_image_and_upload

app = FastAPI(title="Catalog + Inventory (Soft Launch)")

logger = logging.getLogger("catalog_inventory")

_SERVICE = "catalog-inventory"
_REQ_COUNT = Counter("http_requests_total", "Total HTTP requests", ["service", "method", "route", "status"])
_REQ_LATENCY = Histogram("http_request_duration_seconds", "HTTP request duration", ["service", "method", "route"])

_AUTH_SKIP_PATHS = {
    "/health",
    "/metrics",
    "/openapi.json",
    "/docs",
    "/docs/index.html",
    "/redoc",
}
# Temporarily skip auth for media endpoints during testing
_AUTH_SKIP_PREFIXES = ["/catalog/product/", "/catalog/business/", "/catalog/categories", "/inventory/", "/uploads/"]

# Install Python log forwarding to audit-service (best-effort).
try:
    audit_client.install_audit_log_forwarding(service=_SERVICE)
except Exception:
    logger.exception("failed_to_install_audit_log_forwarding")


async def _notify_in_app(*, business_id: str | None, template: str, payload: dict | None, correlation_id: str | None) -> None:
    base = get_notification_base_url().rstrip("/")
    timeout = get_notification_timeout_seconds()
    headers: dict[str, str] = {}
    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            await client.post(
                f"{base}/notification/send",
                json={
                    "channel": "in_app",
                    "user_id": None,
                    "business_id": business_id,
                    "template": template,
                    "payload": payload or {},
                },
                headers=headers,
            )
    except httpx.RequestError:
        logger.info("notification_unreachable", extra={"template": template, "correlation_id": correlation_id})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    start = time.perf_counter()
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = correlation_id

    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    _REQ_COUNT.labels(_SERVICE, request.method, route_path, str(response.status_code)).inc()
    _REQ_LATENCY.labels(_SERVICE, request.method, route_path).observe(time.perf_counter() - start)

    logger.info("request", extra={"method": request.method, "path": route_path, "status": response.status_code, "correlation_id": correlation_id})
    return response


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Require Bearer access tokens issued by msme-engine for all routes except health/metrics/docs.
    if request.url.path in _AUTH_SKIP_PATHS:
        return await call_next(request)
    # Temporarily skip auth for media endpoints during testing
    if any(request.url.path.startswith(prefix) for prefix in _AUTH_SKIP_PREFIXES):
        return await call_next(request)
    try:
        await security.require_access_token(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


async def startup() -> None:
    async with engine.begin() as conn:
        schema = os.getenv("PG_SCHEMA", "").strip()
        if schema and str(engine.url).startswith("postgres"):
            from sqlalchemy import text

            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.run_sync(Base.metadata.create_all)


# Register startup handler without using the deprecated decorator.
app.add_event_handler("startup", startup)


def _correlation_id(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


# ---- Health ----


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


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

        await _notify_in_app(
            business_id=payload.business_id,
            template="catalog_category_created",
            payload={"category_id": cat.id, "name": cat.name},
            correlation_id=_correlation_id(request),
        )
        
        audit_client.emit_audit_sync(
            service="catalog-inventory",
            event_type="category_created",
            payload={
                "category_id": cat.id,
                "business_id": payload.business_id,
                "name": cat.name,
                "parent_id": payload.parent_id,
            },
            metadata={"correlation_id": _correlation_id(request)},
        )
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

        await _notify_in_app(
            business_id=cat.business_id,
            template="catalog_category_updated",
            payload={"category_id": cat.id, **payload.model_dump(exclude_none=True)},
            correlation_id=_correlation_id(request),
        )
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

        await _notify_in_app(
            business_id=cat.business_id,
            template="catalog_category_deleted",
            payload={"category_id": cat.id, "name": cat.name},
            correlation_id=_correlation_id(request),
        )
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
        if not skip_msme_validation():
            # Validate MSME (business) exists
            from src.app.config import get_msme_base_url

            msme_url = get_msme_base_url()
            # Validate MSME exists with a small retry/backoff strategy to be resilient
            # to transient network errors. Treat 404 as not found and 5xx as upstream errors.
            msme_ok = False
            retries = 3
            backoff = 0.1
            async with httpx.AsyncClient(timeout=3.0) as client:
                for attempt in range(retries):
                    try:
                        r = await client.get(f"{msme_url}/business/{payload.business_id}")
                    except httpx.RequestError:
                        if attempt < retries - 1:
                            await asyncio.sleep(backoff * (2 ** attempt))
                            continue
                        raise HTTPException(status_code=502, detail="msme_unreachable")

                    if r.status_code == 200:
                        msme_ok = True
                        break
                    if r.status_code == 404:
                        # Business does not exist
                        raise HTTPException(status_code=404, detail="business_not_found")
                    if 500 <= r.status_code < 600:
                        if attempt < retries - 1:
                            await asyncio.sleep(backoff * (2 ** attempt))
                            continue
                        raise HTTPException(status_code=502, detail="msme_error")
                    # Any other unexpected status considered an upstream error
                    raise HTTPException(status_code=502, detail="msme_error")

            if not msme_ok:
                raise HTTPException(status_code=502, detail="msme_unreachable")

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

        await _notify_in_app(
            business_id=payload.business_id,
            template="catalog_product_created",
            payload={"product_id": prod.id, "name": prod.name, "price": float(prod.price), "currency": prod.currency},
            correlation_id=_correlation_id(request),
        )

        audit_client.emit_audit_sync(
            service="catalog-inventory",
            event_type="product_created",
            payload={
                "product_id": prod.id,
                "business_id": payload.business_id,
                "category_id": payload.category_id,
                "name": prod.name,
                "price": float(prod.price),
                "currency": prod.currency,
            },
            actor_id=None,
            entity_type="product",
            entity_id=prod.id,
            metadata={"correlation_id": _correlation_id(request)},
        )
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

        await _notify_in_app(
            business_id=prod.business_id,
            template="catalog_product_updated",
            payload={"product_id": prod.id, **payload.model_dump(exclude_none=True)},
            correlation_id=_correlation_id(request),
        )
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

        await _notify_in_app(
            business_id=prod.business_id,
            template="catalog_product_deleted",
            payload={"product_id": prod.id, "name": prod.name},
            correlation_id=_correlation_id(request),
        )
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
        
        audit_client.emit_audit_sync(
            service="catalog-inventory",
            event_type="variant_created",
            payload={
                "variant_id": variant.id,
                "product_id": product_id,
                "business_id": prod.business_id,
                "sku": payload.sku,
                "name": payload.name,
            },
            metadata={"correlation_id": _correlation_id(request)},
        )
        return 201, variant

    status, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", "/catalog/product/{id}/variant"),
        key=x_idempotency_key,
        run=_run,
    )
    response.status_code = int(status)
    return body


@app.get("/catalog/product/variant/{variant_id}", response_model=VariantOut)
async def get_variant(variant_id: str, db: AsyncSession = Depends(get_db_session)):
    """Get variant by ID."""
    variant = (await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))).scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="variant_not_found")
    return variant


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


# ---- Uploads (presign + complete) ----


@app.post("/uploads/presign")
async def uploads_presign(payload: dict, request: Request):
    """Return a presigned PUT URL for clients to upload directly to S3/MinIO.

    Expected JSON: {"filename": "name.jpg", "content_type": "image/jpeg"}
    Returns: {"key": "<object-key>", "url": "<presigned-put-url>"}
    """
    filename = payload.get("filename")
    content_type = payload.get("content_type", "application/octet-stream")
    if not filename:
        raise HTTPException(status_code=400, detail="filename_required")

    # Use a UUID-based key to avoid collisions
    key = f"uploads/{str(uuid.uuid4())}-{filename}"
    url = generate_presigned_put_url(key=key, content_type=content_type)
    return {"key": key, "url": url}


@app.post("/uploads/complete")
async def uploads_complete(
    payload: dict,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
):
    """Notify service that an upload finished and request post-processing.

    Expected JSON: {"key": "uploads/..", "product_id": "..."}
    """
    key = payload.get("key")
    product_id = payload.get("product_id")
    if not key:
        raise HTTPException(status_code=400, detail="key_required")

    # process into a thumbnail and attach to product if provided
    thumb_key = key + "-thumb.jpg"
    background.add_task(process_image_and_upload, key, thumb_key, (800, 800))

    if product_id:
        # update product.image_url after processing by creating a presigned GET URL
        # we schedule a small background task to update DB after processing (best-effort)

        async def _attach():
            # wait briefly is not ideal; this assumes processing completes quickly
            # generate a presigned GET URL for the thumbnail
            url = generate_presigned_get_url(thumb_key)
            prod = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
            if prod:
                prod.image_url = url
                await db.commit()
                add_outbox_event(
                    db=db,
                    event_type="catalog.product.image.updated",
                    business_id=prod.business_id,
                    entity_type="product",
                    entity_id=prod.id,
                    correlation_id=getattr(Request, "state", None),
                    meta={"image_key": thumb_key},
                )

        background.add_task(_attach)

    return {"status": "processing", "key": key}


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

        current_stock = int(inv.stock_level)
        current_reserved = int(inv.reserved)
        delta = int(payload.delta)
        reserved_delta = int(payload.reserved_delta or 0)

        new_stock = current_stock + delta
        new_reserved = current_reserved + reserved_delta

        # Hard constraints (prevent oversell / invalid reservation state)
        if new_stock < 0:
            raise HTTPException(status_code=409, detail="insufficient_stock")
        if new_reserved < 0:
            raise HTTPException(status_code=409, detail="reserved_underflow")
        if new_reserved > new_stock:
            # can't reserve more than available stock (or drop stock below reserved)
            raise HTTPException(status_code=409, detail="insufficient_stock")

        inv.stock_level = int(new_stock)
        inv.reserved = int(new_reserved)

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

        # Best-effort: attach a business_id if we can resolve it from variant->product.
        variant = (await db.execute(select(ProductVariant).where(ProductVariant.id == payload.variant_id))).scalar_one_or_none()
        business_id = None
        if variant:
            prod = (await db.execute(select(Product).where(Product.id == variant.product_id))).scalar_one_or_none()
            business_id = prod.business_id if prod else None

        await _notify_in_app(
            business_id=business_id,
            template="inventory_updated",
            payload={
                "variant_id": payload.variant_id,
                "stock_level": int(inv.stock_level),
                "reserved": int(inv.reserved),
                "threshold": int(inv.threshold),
                "reason": payload.reason,
                "meta": payload.meta,
            },
            correlation_id=_correlation_id(request),
        )
        
        audit_client.emit_audit_sync(
            service="catalog-inventory",
            event_type="inventory_updated",
            payload={
                "variant_id": payload.variant_id,
                "business_id": business_id,
                "old_stock": old_stock,
                "new_stock": int(inv.stock_level),
                "delta": int(payload.delta),
                "reserved": int(inv.reserved),
                "reserved_delta": int(payload.reserved_delta or 0),
                "reason": payload.reason,
            },
            entity_type="inventory",
            entity_id=payload.variant_id,
            metadata={"correlation_id": _correlation_id(request)},
        )
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


# ---- Media Upload ----

from fastapi import UploadFile, File
from src.app.nextcloud_client import nextcloud_client
from src.app.schemas import MediaUpload


@app.post("/catalog/product/{product_id}/media", response_model=MediaUploadBatch)
async def product_media_upload(
    product_id: str,
    files: list[UploadFile] = File(...),
    set_default_index: int = 0,
    request: Request = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Upload multiple media files for a product. First file is default unless set_default_index specified."""
    # Verify product exists
    product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    
    if product.media_urls is None:
        product.media_urls = []
    
    # Validate set_default_index
    if set_default_index < 0 or set_default_index >= len(files):
        set_default_index = 0
    
    # If setting new default, unset all existing defaults
    if files:
        for media in product.media_urls:
            media["is_default"] = False
    
    uploaded = []
    
    for idx, file in enumerate(files):
        # Read file content
        file_content = await file.read()
        
        # Upload to Nextcloud
        try:
            url = nextcloud_client.upload_product_media(
                business_id=product.business_id,
                product_id=product_id,
                filename=file.filename,
                file_content=file_content
            )
        except Exception as e:
            logger.error(f"Nextcloud upload failed for {file.filename}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Media upload failed: {str(e)}")
        
        is_default = (idx == set_default_index)
        
        # Create media entry
        media_entry = {
            "url": url,
            "filename": file.filename,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "content_type": file.content_type,
            "size": len(file_content),
            "is_default": is_default
        }
        product.media_urls.append(media_entry)
        
        uploaded.append(MediaUpload(
            url=url,
            filename=file.filename,
            uploaded_at=datetime.now(timezone.utc),
            is_default=is_default
        ))
        
        # Emit audit event for each file
        audit_client.emit_audit_sync(
            service="catalog-inventory",
            event_type="media_uploaded",
            payload={
                "product_id": product_id,
                "business_id": product.business_id,
                "filename": file.filename,
                "url": url,
                "size": len(file_content),
                "is_default": is_default
            },
            metadata={"correlation_id": _correlation_id(request)},
        )
    
    await db.commit()
    await db.refresh(product)
    
    return MediaUploadBatch(
        uploaded=uploaded,
        total=len(uploaded)
    )


@app.delete("/catalog/product/{product_id}/media/{filename}")
async def product_media_delete(
    product_id: str,
    filename: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Delete media file from a product."""
    # Verify product exists
    product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    
    # Delete from Nextcloud
    success = nextcloud_client.delete_product_media(
        business_id=product.business_id,
        product_id=product_id,
        filename=filename
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="media_not_found")
    
    # Check if deleted file was the default
    was_default = False
    if product.media_urls:
        was_default = any(m.get("filename") == filename and m.get("is_default") for m in product.media_urls)
        
        # Remove from product media_urls (create new list)
        new_media_urls = [
            m for m in product.media_urls 
            if m.get("filename") != filename
        ]
        
        # If we deleted the default and there are other files, set first as default
        if was_default and new_media_urls:
            # Create a copy of the first media dict and update it
            new_media_urls = [
                {**m, "is_default": i == 0} for i, m in enumerate(new_media_urls)
            ]
        
        # Reassign to trigger SQLAlchemy change tracking
        product.media_urls = new_media_urls
        await db.commit()
    
    # Emit audit event
    audit_client.emit_audit_sync(
        service="catalog-inventory",
        event_type="media_deleted",
        payload={
            "product_id": product_id,
            "business_id": product.business_id,
            "filename": filename
        },
        metadata={"correlation_id": _correlation_id(request)},
    )
    
    return {"status": "deleted", "filename": filename}


@app.patch("/catalog/product/{product_id}/media/{filename}/set-default")
async def product_media_set_default(
    product_id: str,
    filename: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Set a specific media file as the default for a product."""
    # Verify product exists
    product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    
    if not product.media_urls:
        raise HTTPException(status_code=404, detail="no_media_found")
    
    # Find the media to set as default (create new list with updated dicts)
    media_found = False
    new_media_urls = []
    
    for media in product.media_urls:
        if media.get("filename") == filename:
            # Create new dict with is_default=True
            new_media_urls.append({**media, "is_default": True})
            media_found = True
        else:
            # Create new dict with is_default=False
            new_media_urls.append({**media, "is_default": False})
    
    if not media_found:
        raise HTTPException(status_code=404, detail="media_not_found")
    
    # Reassign to trigger SQLAlchemy change tracking
    product.media_urls = new_media_urls
    await db.commit()
    await db.refresh(product)
    
    # Emit audit event
    audit_client.emit_audit_sync(
        service="catalog-inventory",
        event_type="media_default_set",
        payload={
            "product_id": product_id,
            "business_id": product.business_id,
            "filename": filename
        },
        metadata={"correlation_id": _correlation_id(request)},
    )
    
    return {"status": "updated", "filename": filename, "is_default": True}


# ---- Outbox events (debug) ----


@app.get("/events", response_model=list[OutboxEventOut])
async def events_list(limit: int = 100, db: AsyncSession = Depends(get_db_session)):
    stmt = select(OutboxEvent).order_by(OutboxEvent.created_at.desc()).limit(int(limit))
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)
