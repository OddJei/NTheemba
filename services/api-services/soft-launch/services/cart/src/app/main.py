from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from src.app.db import Base, engine, get_db_session
from src.app.idempotency import idempotent_execute, scope_for
from src.app.models import Cart, CartItem
from src.app.schemas import CartCreate, CartOut, CartItemCreate, CartItemOut, CheckoutOut
from src.app import events
from src.app import config as _config

app = FastAPI(title="Cart Service (Soft Launch)")

logger = logging.getLogger("cart")

_SERVICE = "cart"
_REQ_COUNT = Counter("http_requests_total", "Total HTTP requests", ["service", "method", "route", "status"])
_REQ_LATENCY = Histogram("http_request_duration_seconds", "HTTP request duration", ["service", "method", "route"])


async def _inventory_update(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    payload: dict,
    correlation_id: str | None,
    idempotency_key: str | None = None,
) -> None:
    headers: dict[str, str] = {}
    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id
    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key

    try:
        resp = await client.post(f"{base_url}/inventory/update", json=payload, headers=headers)
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="inventory_service_unavailable")

    if resp.status_code == 409:
        # catalog-inventory uses 409 for insufficient stock / reserve violations
        raise HTTPException(status_code=409, detail="insufficient_stock")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="inventory_update_failed")


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


@app.on_event("startup")
async def startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/cart/create", response_model=CartOut)
async def cart_create(
    payload: CartCreate,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        cart = Cart(
            session_id=payload.session_id,
            user_phone=payload.user_phone,
            business_id=payload.business_id,
            status="active",
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        db.add(cart)
        await db.commit()
        await db.refresh(cart)
        return 201, cart

    status, body = await idempotent_execute(db=db, scope=scope_for("POST", "/cart/create"), key=x_idempotency_key, run=_run)
    response.status_code = int(status)
    return body


@app.post("/cart/{cart_id}/add", response_model=CartItemOut)
async def cart_add_item(
    cart_id: str,
    payload: CartItemCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        cart = (await db.execute(select(Cart).where(Cart.id == cart_id))).scalar_one_or_none()
        if not cart:
            raise HTTPException(status_code=404, detail="cart_not_found")

        # Reserve inventory for this item
        catalog_url = _config.get_catalog_base_url()
        correlation_id = getattr(request.state, "correlation_id", None)
        async with httpx.AsyncClient(timeout=5.0) as client:
            await _inventory_update(
                client=client,
                base_url=catalog_url,
                payload={
                    "variant_id": payload.variant_id,
                    "delta": 0,
                    "reserved_delta": int(payload.quantity),
                    "reason": "cart_reserve",
                    "meta": {"cart_id": cart_id},
                },
                correlation_id=correlation_id,
                idempotency_key=(f"{x_idempotency_key}:reserve" if x_idempotency_key else None),
            )

        item = CartItem(
            cart_id=cart_id,
            variant_id=payload.variant_id,
            quantity=payload.quantity,
            reserved_quantity=payload.quantity,
            unit_price=payload.unit_price,
            subtotal=payload.unit_price * payload.quantity,
            created_at=_utcnow(),
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return 200, item

    status, body = await idempotent_execute(db=db, scope=scope_for("POST", "/cart/{id}/add"), key=x_idempotency_key, run=_run)
    response.status_code = int(status)
    return body


@app.put("/cart/{cart_id}/update", response_model=CartItemOut)
async def cart_update_item(cart_id: str, payload: CartItemCreate, request: Request, db: AsyncSession = Depends(get_db_session)):
    item = (
        await db.execute(select(CartItem).where(CartItem.cart_id == cart_id, CartItem.variant_id == payload.variant_id))
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="item_not_found")

    diff = int(payload.quantity) - int(item.quantity)
    if diff != 0:
        catalog_url = _config.get_catalog_base_url()
        async with httpx.AsyncClient(timeout=5.0) as client:
            await _inventory_update(
                client=client,
                base_url=catalog_url,
                payload={
                    "variant_id": item.variant_id,
                    "delta": 0,
                    "reserved_delta": int(diff),
                    "reason": "cart_adjust_reserve",
                    "meta": {"cart_id": cart_id},
                },
                correlation_id=getattr(request.state, "correlation_id", None),
            )
        item.reserved_quantity = int(item.reserved_quantity) + int(diff)

    item.quantity = payload.quantity
    item.unit_price = payload.unit_price
    item.subtotal = payload.quantity * payload.unit_price
    await db.commit()
    await db.refresh(item)
    return item


@app.delete("/cart/{cart_id}/remove/{item_id}")
async def cart_remove_item(cart_id: str, item_id: str, request: Request, db: AsyncSession = Depends(get_db_session)):
    item = (await db.execute(select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="item_not_found")

    # Release reserved inventory
    if int(item.reserved_quantity) > 0:
        catalog_url = _config.get_catalog_base_url()
        async with httpx.AsyncClient(timeout=5.0) as client:
            await _inventory_update(
                client=client,
                base_url=catalog_url,
                payload={
                    "variant_id": item.variant_id,
                    "delta": 0,
                    "reserved_delta": -int(item.reserved_quantity),
                    "reason": "cart_release_reserve",
                    "meta": {"cart_id": cart_id},
                },
                correlation_id=getattr(request.state, "correlation_id", None),
            )

    await db.delete(item)
    await db.commit()
    return {"status": "removed", "item_id": item_id}


@app.get("/cart/session/{session_id}", response_model=list[CartOut])
async def cart_by_session(session_id: str, db: AsyncSession = Depends(get_db_session)):
    rows = (await db.execute(select(Cart).where(Cart.session_id == session_id))).scalars().all()
    return list(rows)


@app.get("/cart/user/{user_phone}", response_model=list[CartOut])
async def cart_by_user(user_phone: str, db: AsyncSession = Depends(get_db_session)):
    rows = (await db.execute(select(Cart).where(Cart.user_phone == user_phone))).scalars().all()
    return list(rows)


@app.post("/cart/{cart_id}/checkout", response_model=CheckoutOut)
async def cart_checkout(cart_id: str, request: Request, db: AsyncSession = Depends(get_db_session)):
    """Validate inventory for items, mark cart checked_out and enqueue outbox event."""
    cart = (await db.execute(select(Cart).where(Cart.id == cart_id))).scalar_one_or_none()
    if not cart:
        raise HTTPException(status_code=404, detail="cart_not_found")
    items = (await db.execute(select(CartItem).where(CartItem.cart_id == cart_id))).scalars().all()
    if not items:
        raise HTTPException(status_code=400, detail="empty_cart")

    total = sum(float(i.subtotal) for i in items)

    catalog_url = _config.get_catalog_base_url()
    correlation_id = getattr(request.state, "correlation_id", None)

    # Confirm checkout: ensure items are reserved, then decrement stock and release reserved.
    async with httpx.AsyncClient(timeout=5.0) as client:
        for item in items:
            missing = int(item.quantity) - int(item.reserved_quantity)
            if missing > 0:
                await _inventory_update(
                    client=client,
                    base_url=catalog_url,
                    payload={
                        "variant_id": item.variant_id,
                        "delta": 0,
                        "reserved_delta": int(missing),
                        "reason": "checkout_reserve_missing",
                        "meta": {"cart_id": cart_id},
                    },
                    correlation_id=correlation_id,
                )
                item.reserved_quantity = int(item.reserved_quantity) + int(missing)

            await _inventory_update(
                client=client,
                base_url=catalog_url,
                payload={
                    "variant_id": item.variant_id,
                    "delta": -int(item.quantity),
                    "reserved_delta": -int(item.quantity),
                    "reason": "checkout_confirm",
                    "meta": {"cart_id": cart_id},
                },
                correlation_id=correlation_id,
            )
            item.reserved_quantity = max(0, int(item.reserved_quantity) - int(item.quantity))

    cart.status = "checked_out"
    cart.updated_at = _utcnow()
    await db.commit()

    # enqueue outbox event for downstream processing
    payload = {"cart_id": cart_id, "items": [{"variant_id": i.variant_id, "quantity": i.quantity, "subtotal": float(i.subtotal)} for i in items], "total": total}
    await events.add_outbox_event(db, event_type="cart.checked_out", payload=payload, business_id=cart.business_id, entity_type="cart", entity_id=cart_id, correlation_id=getattr(request.state, "correlation_id", None))

    return CheckoutOut(status="checked_out", cart_id=cart_id, total=total)
