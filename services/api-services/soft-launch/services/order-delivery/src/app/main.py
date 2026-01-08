from __future__ import annotations

import hashlib
import logging
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text, inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.db import Base, engine, get_db_session
from src.app.idempotency import idempotent_execute, scope_for
from src.app.models import Delivery, Order, OutboxEvent
from src.app.schemas import (
    DeliveryConfirmIn,
    DeliveryInitiateOut,
    DeliveryOut,
    OrderCreate,
    OrderOut,
    StatusOut,
)

app = FastAPI(title="Order + Delivery Service (Soft Launch)")

logger = logging.getLogger("order-delivery")

_SERVICE = "order_delivery"
_REQ_COUNT = Counter("http_requests_total", "Total HTTP requests", ["service", "method", "route", "status"])
_REQ_LATENCY = Histogram("http_request_duration_seconds", "HTTP request duration", ["service", "method", "route"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_delivery_code() -> str:
    # 6 digits; simple for soft-launch. (Can switch to hash storage later.)
    return f"{secrets.randbelow(1_000_000):06d}"


def _new_salt_hex() -> str:
    return secrets.token_hex(16)


def _hash_delivery_code(*, salt_hex: str, code: str) -> str:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.sha256(salt + code.encode("utf-8")).hexdigest()
    return digest


def _verify_delivery_code(*, delivery: Delivery, code: str) -> bool:
    # Backward-compatible: accept cleartext storage if present.
    if delivery.delivery_code is not None:
        return secrets.compare_digest(delivery.delivery_code, code)
    if not delivery.delivery_code_salt or not delivery.delivery_code_hash:
        return False
    expected = _hash_delivery_code(salt_hex=delivery.delivery_code_salt, code=code)
    return secrets.compare_digest(delivery.delivery_code_hash, expected)


async def _ensure_delivery_hash_columns() -> None:
    # SQLite: existing local DB may have been created before these columns existed.
    async with engine.begin() as conn:
        res = await conn.execute(text("PRAGMA table_info(deliveries)"))
        existing = {row[1] for row in res.fetchall()}
        if "delivery_code_salt" not in existing:
            await conn.execute(text("ALTER TABLE deliveries ADD COLUMN delivery_code_salt TEXT"))
        if "delivery_code_hash" not in existing:
            await conn.execute(text("ALTER TABLE deliveries ADD COLUMN delivery_code_hash TEXT"))


async def _emit_outbox(db: AsyncSession, *, event_type: str, payload: dict) -> None:
    db.add(OutboxEvent(event_type=event_type, payload=payload, processed=False, created_at=_utcnow()))


def _serialize_order(order: Order) -> dict:
    state = inspect(order)
    return {
        "id": order.id,
        "session_id": getattr(order, "session_id", None),
        "user_phone": getattr(order, "user_phone", None),
        "user_id": getattr(order, "user_id", None),
        "business_id": getattr(order, "business_id", None),
        "status": getattr(order, "status", None),
        "delivery_method": getattr(order, "delivery_method", None),
        "total_amount": getattr(order, "total_amount", None),
        "currency": getattr(order, "currency", None),
        "metadata": (state.attrs.meta.value if hasattr(state.attrs, "meta") else {}),
        "created_at": getattr(order, "created_at", None),
        "updated_at": getattr(order, "updated_at", None),
    }


def _serialize_delivery(delivery: Delivery) -> dict:
    state = inspect(delivery)
    return {
        "id": delivery.id,
        "order_id": getattr(delivery, "order_id", None),
        "user_phone": getattr(delivery, "user_phone", None),
        "user_id": getattr(delivery, "user_id", None),
        "business_id": getattr(delivery, "business_id", None),
        "delivery_method": getattr(delivery, "delivery_method", None),
        "status": getattr(delivery, "status", None),
        "confirmed_by": getattr(delivery, "confirmed_by", None),
        "metadata": (state.attrs.meta.value if hasattr(state.attrs, "meta") else {}),
        "created_at": getattr(delivery, "created_at", None),
        "updated_at": getattr(delivery, "updated_at", None),
    }


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

    logger.info(
        "request",
        extra={"method": request.method, "path": route_path, "status": response.status_code, "correlation_id": correlation_id},
    )
    return response


@app.on_event("startup")
async def startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_delivery_hash_columns()


@app.get("/health")
async def health() -> StatusOut:
    return StatusOut(status="ok")


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/orders/create", response_model=OrderOut)
async def order_create(
    payload: OrderCreate,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        now = _utcnow()
        order = Order(
            session_id=payload.session_id,
            user_phone=payload.user_phone,
            user_id=payload.user_id,
            business_id=payload.business_id,
            status="pending_payment",
            delivery_method=payload.delivery_method,
            total_amount=int(payload.total_amount),
            currency=payload.currency,
            meta=payload.meta,
            created_at=now,
            updated_at=now,
        )
        db.add(order)
        await _emit_outbox(
            db,
            event_type="order_created",
            payload={"order_id": order.id, "business_id": order.business_id, "user_phone": order.user_phone},
        )
        await db.commit()
        await db.refresh(order)
        return 201, OrderOut(**_serialize_order(order))

    status, body = await idempotent_execute(db=db, scope=scope_for("POST", "/orders/create"), key=x_idempotency_key, run=_run)
    response.status_code = int(status)
    return body


@app.get("/orders/{order_id}", response_model=OrderOut)
async def order_get(order_id: str, db: AsyncSession = Depends(get_db_session)):
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")
    return OrderOut(**_serialize_order(order))


@app.post("/orders/{order_id}/mark_paid", response_model=OrderOut)
async def order_mark_paid(order_id: str, db: AsyncSession = Depends(get_db_session)):
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")

    if order.status == "pending_payment":
        order.status = "paid"
        order.updated_at = _utcnow()
        await _emit_outbox(db, event_type="order_paid", payload={"order_id": order.id, "business_id": order.business_id})
        await db.commit()
        await db.refresh(order)

    return OrderOut(**_serialize_order(order))


@app.post("/delivery/initiate/{order_id}", response_model=DeliveryInitiateOut)
async def delivery_initiate(
    order_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="order_not_found")
        if order.status != "paid":
            raise HTTPException(status_code=400, detail="order_not_paid")

        existing = (await db.execute(select(Delivery).where(Delivery.order_id == order_id))).scalar_one_or_none()
        if existing:
            # For idempotency callers that lost the delivery code, we cannot safely re-return it.
            # Soft-launch: return a masked code marker.
            return 200, {"delivery": existing, "delivery_code": "******"}

        now = _utcnow()
        # Generate a code and store only a salted hash.
        # Collision risk is low but still possible; loop defensively.
        for _ in range(25):
            code = _new_delivery_code()
            salt_hex = _new_salt_hex()
            code_hash = _hash_delivery_code(salt_hex=salt_hex, code=code)
            dup = (
                await db.execute(select(Delivery).where(Delivery.delivery_code_hash == code_hash))
            ).scalar_one_or_none()
            if not dup:
                break
        else:
            raise HTTPException(status_code=500, detail="delivery_code_generation_failed")

        delivery = Delivery(
            order_id=order.id,
            user_phone=order.user_phone,
            user_id=order.user_id,
            business_id=order.business_id,
            delivery_method=order.delivery_method,
            delivery_code=None,
            delivery_code_salt=salt_hex,
            delivery_code_hash=code_hash,
            status="code_sent",
            confirmed_by=None,
            meta={"order_total": order.total_amount, "currency": order.currency},
            created_at=now,
            updated_at=now,
        )
        db.add(delivery)
        await _emit_outbox(
            db,
            event_type="delivery_code_generated",
            payload={
                "delivery_id": delivery.id,
                "order_id": order.id,
                "business_id": order.business_id,
                "user_phone": order.user_phone,
                "delivery_method": order.delivery_method,
            },
        )
        await db.commit()
        await db.refresh(delivery)
        return 201, {"delivery": DeliveryOut(**_serialize_delivery(delivery)), "delivery_code": code}

    status, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", "/delivery/initiate/{order_id}"),
        key=x_idempotency_key,
        run=_run,
    )
    response.status_code = int(status)
    return DeliveryInitiateOut(delivery=body["delivery"], delivery_code=body["delivery_code"]) if isinstance(body, dict) else body


@app.get("/delivery/{delivery_id}", response_model=DeliveryOut)
async def delivery_get(delivery_id: str, db: AsyncSession = Depends(get_db_session)):
    delivery = (await db.execute(select(Delivery).where(Delivery.id == delivery_id))).scalar_one_or_none()
    if not delivery:
        raise HTTPException(status_code=404, detail="delivery_not_found")
    return DeliveryOut(**_serialize_delivery(delivery))


@app.get("/delivery/order/{order_id}", response_model=DeliveryOut)
async def delivery_by_order(order_id: str, db: AsyncSession = Depends(get_db_session)):
    delivery = (await db.execute(select(Delivery).where(Delivery.order_id == order_id))).scalar_one_or_none()
    if not delivery:
        raise HTTPException(status_code=404, detail="delivery_not_found")
    return DeliveryOut(**_serialize_delivery(delivery))


@app.get("/delivery/user/{user_phone}", response_model=list[DeliveryOut])
async def deliveries_by_user(user_phone: str, db: AsyncSession = Depends(get_db_session)):
    rows = (await db.execute(select(Delivery).where(Delivery.user_phone == user_phone))).scalars().all()
    return [DeliveryOut(**_serialize_delivery(r)) for r in rows]


@app.post("/delivery/{delivery_id}/confirm", response_model=DeliveryOut)
async def delivery_confirm(delivery_id: str, payload: DeliveryConfirmIn, db: AsyncSession = Depends(get_db_session)):
    delivery = (await db.execute(select(Delivery).where(Delivery.id == delivery_id))).scalar_one_or_none()
    if not delivery:
        raise HTTPException(status_code=404, detail="delivery_not_found")

    if delivery.status == "confirmed":
        return DeliveryOut(**_serialize_delivery(delivery))

    if not _verify_delivery_code(delivery=delivery, code=payload.delivery_code):
        raise HTTPException(status_code=400, detail="invalid_delivery_code")

    order = (await db.execute(select(Order).where(Order.id == delivery.order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")

    delivery.status = "confirmed"
    delivery.confirmed_by = payload.confirmed_by
    delivery.updated_at = _utcnow()

    if order.status != "delivered":
        order.status = "delivered"
        order.updated_at = _utcnow()

    await _emit_outbox(
        db,
        event_type="delivery_confirmed",
        payload={"delivery_id": delivery.id, "order_id": order.id, "business_id": order.business_id},
    )
    await _emit_outbox(
        db,
        event_type="order_delivered",
        payload={"order_id": order.id, "business_id": order.business_id},
    )

    await db.commit()
    await db.refresh(delivery)
    return DeliveryOut(**_serialize_delivery(delivery))
