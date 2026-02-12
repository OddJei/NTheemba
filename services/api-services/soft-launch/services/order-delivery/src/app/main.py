from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text, inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.config import (
    get_affiliate_engine_base_url,
    get_affiliate_engine_timeout_seconds,
    get_bot_session_base_url,
    get_bot_session_timeout_seconds,
    get_internal_service_secret,
    get_msme_base_url,
    get_msme_timeout_seconds,
    get_notification_base_url,
    get_notification_timeout_seconds,
    get_outbox_dispatch_batch_size,
    get_outbox_dispatch_enabled,
    get_outbox_dispatch_interval_seconds,
    get_payment_revenue_base_url,
    get_payment_revenue_timeout_seconds,
    get_pg_schema,
)
from src.app.db import Base, engine, get_db_session
from src.app.idempotency import idempotent_execute, scope_for
from src.app.models import Delivery, Order, OutboxEvent
from src.app.schemas import (
    DeliveryConfirmIn,
    DeliveryInitiateOut,
    DeliveryOut,
    OrderCreate,
    OrderOut,
    PaymentInitiateIn,
    PaymentStatusOut,
    StatusOut,
)
from src.app import audit_client
from src.app import security
from src.app import outbox_dispatcher

app = FastAPI(title="Order + Delivery Service (Soft Launch)")

logger = logging.getLogger("order-delivery")

_SERVICE = "order_delivery"
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

_outbox_task: asyncio.Task | None = None


def _authorize_business_access(request: Request, business_id: str) -> None:
    token_payload = getattr(request.state, "token_payload", {}) or {}
    if not token_payload:
        raise HTTPException(status_code=401, detail="missing_token_payload")

    caller_role = token_payload.get("role")
    if caller_role in ("admin", "msme", "staff"):
        return

    caller_business = token_payload.get("business_id") or request.headers.get("X-Business-Id")
    if not caller_business:
        raise HTTPException(status_code=401, detail="business_auth_required")
    if str(caller_business) != str(business_id):
        raise HTTPException(status_code=403, detail="forbidden")


async def _notify_in_app(*, user_id: str | None, business_id: str | None, template: str, payload: dict | None, correlation_id: str | None) -> None:
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
                    "user_id": user_id,
                    "business_id": business_id,
                    "template": template,
                    "payload": payload or {},
                },
                headers=headers,
            )
    except httpx.RequestError:
        logger.info("notification_unreachable", extra={"template": template, "correlation_id": correlation_id})


def _require_internal_secret_od(request: Request) -> None:
    expected = (get_internal_service_secret() or "").strip()
    provided = (request.headers.get("X-Internal-Secret") or "").strip()
    if expected and (not provided or not secrets.compare_digest(expected, provided)):
        raise HTTPException(status_code=401, detail="invalid_internal_secret")


@app.get("/outbox/pending")
async def outbox_pending_od(request: Request, batch_size: int = 50, db: AsyncSession = Depends(get_db_session)):
    _require_internal_secret_od(request)
    q = select(OutboxEvent).where(OutboxEvent.processed == False)
    q = q.order_by(OutboxEvent.created_at).limit(int(batch_size))
    rows = (await db.execute(q)).scalars().all()
    out = []
    for r in rows:
        out.append({
            "id": r.id,
            "event_type": r.event_type,
            "payload": r.payload,
            "dedupe_key": None,
            "destination": None,
            "attempts": 0,
            "scheduled_at": None,
            "correlation_id": r.payload.get("correlation_id") if isinstance(r.payload, dict) else None,
        })
    return out


@app.post("/outbox/ack")
async def outbox_ack_od(request: Request, body: dict, db: AsyncSession = Depends(get_db_session)):
    _require_internal_secret_od(request)
    ids = body.get("ids") or []
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="invalid_ids")
    q = select(OutboxEvent).where(OutboxEvent.id.in_(ids))
    rows = (await db.execute(q)).scalars().all()
    for r in rows:
        r.processed = True
    await db.commit()
    return {"acked": [r.id for r in rows]}


def _extract_affiliate_code(meta: dict | None) -> str | None:
    if not meta:
        return None

    value = meta.get("affiliate_code")
    if isinstance(value, str) and value.strip():
        return value.strip()

    value = meta.get("affiliateCode")
    if isinstance(value, str) and value.strip():
        return value.strip()

    value = meta.get("affiliate")
    if isinstance(value, dict):
        code = value.get("code")
        if isinstance(code, str) and code.strip():
            return code.strip()

    return None


def _extract_affiliate_id(meta: dict | None) -> str | None:
    if not meta:
        return None

    value = meta.get("affiliate_id")
    if isinstance(value, str) and value.strip():
        return value.strip()

    value = meta.get("affiliateId")
    if isinstance(value, str) and value.strip():
        return value.strip()

    value = meta.get("affiliate")
    if isinstance(value, dict):
        aff_id = value.get("id") or value.get("affiliate_id")
        if isinstance(aff_id, str) and aff_id.strip():
            return aff_id.strip()

    return None


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Require Bearer access tokens issued by msme-engine for all routes except health/metrics/docs.
    # Skip auth for exact paths and for /orders/{id}/mark_paid pattern
    path = request.url.path
    if path in _AUTH_SKIP_PATHS:
        return await call_next(request)
    # Pattern: /orders/{order_id}/mark_paid
    if path.startswith("/orders/") and path.endswith("/mark_paid"):
        return await call_next(request)

    expected_internal = (get_internal_service_secret() or "").strip()
    if expected_internal:
        provided_internal = (request.headers.get("X-Internal-Secret") or "").strip()
        if provided_internal and secrets.compare_digest(provided_internal, expected_internal):
            return await call_next(request)
    try:
        await security.require_access_token(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


async def _dispatch_to_affiliate_engine_order_created(*, payload: dict, correlation_id: str) -> bool:
    base = get_affiliate_engine_base_url().rstrip("/")
    timeout = get_affiliate_engine_timeout_seconds()

    headers: dict[str, str] = {"X-Correlation-Id": correlation_id}
    event_id = payload.get("event_id")
    if isinstance(event_id, str) and event_id:
        headers["X-Idempotency-Key"] = event_id

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{base}/events/order-created", json=payload, headers=headers)
    except httpx.RequestError:
        logger.info("affiliate_engine_unreachable", extra={"correlation_id": correlation_id})
        return False

    if r.status_code in (200, 201):
        return True

    # Affiliate engine will return 200 ignored when no affiliate_code.
    logger.info(
        "affiliate_engine_order_created_failed",
        extra={"status": r.status_code, "correlation_id": correlation_id},
    )
    return False


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


def _fee_amount_minor_units(*, total_amount: int, fee_bps: int) -> int:
    # Rounds to nearest minor unit.
    if total_amount <= 0 or fee_bps <= 0:
        return 0
    return int((total_amount * fee_bps + 5000) // 10000)


async def _get_transaction_fee_bps_for_business(*, business_id: str) -> tuple[int, str]:
    # Returns (fee_bps, source). Safe fallback to free tier if MSME is unavailable.
    msme_url = get_msme_base_url().rstrip("/")
    timeout = get_msme_timeout_seconds()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{msme_url}/business/{business_id}/entitlements")
    except httpx.RequestError:
        return 700, "fallback_free_msme_unreachable"

    if r.status_code == 200:
        try:
            ent = r.json() if isinstance(r.json(), dict) else {}
        except ValueError:
            ent = {}
        pct = ent.get("transaction_fee_pct")
        try:
            fee_bps = int(round(float(pct) * 10000))
        except (TypeError, ValueError):
            fee_bps = 700
        # Clamp to expected policy values.
        if fee_bps not in (500, 700):
            fee_bps = 700
        return fee_bps, "msme_entitlements"

    if r.status_code == 404:
        return 700, "fallback_free_business_not_found"
    return 700, "fallback_free_msme_error"


async def _ensure_delivery_hash_columns() -> None:
    # Best-effort migration for older DBs.
    async with engine.begin() as conn:
        if engine.dialect.name.startswith("sqlite"):
            res = await conn.execute(text("PRAGMA table_info(deliveries)"))
            existing = {row[1] for row in res.fetchall()}
            if "delivery_code_salt" not in existing:
                await conn.execute(text("ALTER TABLE deliveries ADD COLUMN delivery_code_salt TEXT"))
            if "delivery_code_hash" not in existing:
                await conn.execute(text("ALTER TABLE deliveries ADD COLUMN delivery_code_hash TEXT"))
            return

        if engine.dialect.name.startswith("postgres"):
            schema = get_pg_schema() or "public"
            await conn.execute(
                text(f'ALTER TABLE IF EXISTS "{schema}".deliveries ADD COLUMN IF NOT EXISTS delivery_code_salt TEXT')
            )
            await conn.execute(
                text(f'ALTER TABLE IF EXISTS "{schema}".deliveries ADD COLUMN IF NOT EXISTS delivery_code_hash TEXT')
            )
            return

        # For other DBs, no-op.
        return


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


async def startup() -> None:
    async with engine.begin() as conn:
        schema = get_pg_schema()
        if schema and engine.dialect.name.startswith("postgres"):
            # Allow only letters, numbers, underscore to avoid SQL injection.
            if not __import__("re").fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
                raise RuntimeError("invalid_pg_schema")
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_delivery_hash_columns()

    if get_outbox_dispatch_enabled():
        global _outbox_task
        if _outbox_task is None or _outbox_task.done():
            logger.info("STARTUP_DISPATCHER_ENABLED", extra={"interval_sec": get_outbox_dispatch_interval_seconds(), "batch_size": get_outbox_dispatch_batch_size()})
            _outbox_task = asyncio.create_task(
                outbox_dispatcher.run_forever(
                    poll_seconds=get_outbox_dispatch_interval_seconds(),
                    batch_size=get_outbox_dispatch_batch_size(),
                )
            )


async def shutdown() -> None:
    global _outbox_task
    if _outbox_task and not _outbox_task.done():
        _outbox_task.cancel()
        try:
            await _outbox_task
        except asyncio.CancelledError:
            pass


# Register startup handler without using the deprecated decorator.
app.add_event_handler("startup", startup)
app.add_event_handler("shutdown", shutdown)


@app.get("/health")
async def health() -> StatusOut:
    return StatusOut(status="ok")


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/orders/create", response_model=OrderOut)
async def order_create(
    payload: OrderCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        now = _utcnow()
        fee_bps, fee_source = await _get_transaction_fee_bps_for_business(business_id=payload.business_id)
        fee_amount = _fee_amount_minor_units(total_amount=int(payload.total_amount), fee_bps=fee_bps)
        meta = dict(payload.meta or {})
        meta.setdefault("transaction_fee_pct", fee_bps / 10000)
        meta.setdefault("platform_fee_amount", fee_amount)
        meta.setdefault("msme_net_amount", int(payload.total_amount) - fee_amount)
        meta.setdefault("fee_source", fee_source)

        order = Order(
            session_id=payload.session_id,
            user_phone=payload.user_phone,
            user_id=payload.user_id,
            business_id=payload.business_id,
            status="pending_payment",
            delivery_method=payload.delivery_method,
            total_amount=int(payload.total_amount),
            currency=payload.currency,
            meta=meta,
            created_at=now,
            updated_at=now,
        )
        db.add(order)

        # Assign `order.id` before we emit outbox events referencing it.
        await db.flush()

        # If session_id provided and no affiliate in meta, try to fetch latest cycle attribution
        try:
            if payload.session_id and not _extract_affiliate_code(meta):
                bot_base = get_bot_session_base_url().rstrip("/")
                timeout = get_bot_session_timeout_seconds()
                async with httpx.AsyncClient(timeout=timeout) as client:
                    r = await client.get(f"{bot_base}/session/{payload.session_id}/cycles")
                    if r.status_code == 200:
                        cycles = r.json() or []
                        if cycles:
                            last = cycles[-1]
                            aff_code = last.get("affiliate_code")
                            aff_id = last.get("affiliate_id")
                            aff_meta = last.get("meta")
                            if aff_code:
                                meta.setdefault("affiliate_code", aff_code)
                            if aff_meta:
                                meta.setdefault("affiliate_metadata", aff_meta)
                            if aff_id:
                                meta.setdefault("affiliate_id", aff_id)
                                
        except Exception:
            # Best-effort: ignore failures to reach bot-session
            pass

        correlation_id = getattr(request.state, "correlation_id", None)
        affiliate_code = _extract_affiliate_code(meta)
        affiliate_id = _extract_affiliate_id(meta)

        # Keep the outbox event, but enrich it with affiliate attribution fields so a dispatcher can
        # reliably forward to affiliate-engine when available.
        outbox_event = OutboxEvent(
            event_type="order_created",
            processed=False,
            created_at=now,
            payload={
                "event_id": f"order-created-{order.id}",
                "event_type": "order_created",
                "occurred_at": now.isoformat().replace("+00:00", "Z"),
                "correlation_id": correlation_id or str(uuid.uuid4()),
                "producer": "order-delivery",
                "order_id": order.id,
                "business_id": order.business_id,
                "status": order.status,
                "total_amount": float(order.total_amount),
                "currency": order.currency,
                "session_id": order.session_id,
                "user_phone": order.user_phone,
                "user_id": order.user_id,
                "affiliate_code": affiliate_code,
                "affiliate_id": affiliate_id,
                "metadata": meta,
                "transaction_fee_pct": meta.get("transaction_fee_pct"),
                "platform_fee_amount": meta.get("platform_fee_amount"),
                "msme_net_amount": meta.get("msme_net_amount"),
            },
        )
        db.add(outbox_event)
        await db.commit()
        await db.refresh(order)

        # Best-effort immediate dispatch to affiliate-engine for attribution.
        if affiliate_code and correlation_id:
            ok = await _dispatch_to_affiliate_engine_order_created(payload=outbox_event.payload, correlation_id=correlation_id)
            if ok:
                outbox_event.processed = True
                await db.commit()

        await _notify_in_app(
            user_id=order.user_id or order.user_phone,
            business_id=order.business_id,
            template="order_created",
            payload={"order_id": order.id, "total_amount": order.total_amount, "currency": order.currency},
            correlation_id=correlation_id,
        )
        await audit_client.emit_audit(
            service="order-delivery",
            event_type="order_created",
            payload={"order_id": order.id, "business_id": order.business_id, "total_amount": order.total_amount},
            actor_id=order.user_id or order.user_phone,
            entity_type="order",
            entity_id=order.id,
            metadata={"correlation_id": correlation_id, "affiliate_code": affiliate_code},
        )
        return 201, OrderOut(**_serialize_order(order))

    status, body = await idempotent_execute(db=db, scope=scope_for("POST", "/orders/create"), key=x_idempotency_key, run=_run)
    response.status_code = int(status)
    return body


@app.get("/orders/pending", response_model=list[OrderOut])
async def list_pending_orders(request: Request, business_id: str, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db_session)) -> list[OrderOut]:
    """List orders for `business_id` that are pending payment (for MSME dashboard)."""
    if not business_id:
        raise HTTPException(status_code=400, detail="business_id_required")
    _authorize_business_access(request, business_id)
    res = await db.execute(
        select(Order)
        .where(Order.business_id == business_id, Order.status == "pending_payment")
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = res.scalars().all()
    return [OrderOut(**_serialize_order(o)) for o in items]


@app.get("/orders/{order_id}", response_model=OrderOut)
async def order_get(order_id: str, db: AsyncSession = Depends(get_db_session)):
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")
    return OrderOut(**_serialize_order(order))


@app.post("/orders/{order_id}/mark_paid", response_model=OrderOut)
async def order_mark_paid(order_id: str, request: Request, db: AsyncSession = Depends(get_db_session)):
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")

    if order.status == "pending_payment":
        meta = dict(order.meta or {})
        if "platform_fee_amount" not in meta or "transaction_fee_pct" not in meta:
            fee_bps, fee_source = await _get_transaction_fee_bps_for_business(business_id=order.business_id)
            fee_amount = _fee_amount_minor_units(total_amount=int(order.total_amount), fee_bps=fee_bps)
            meta.setdefault("transaction_fee_pct", fee_bps / 10000)
            meta.setdefault("platform_fee_amount", fee_amount)
            meta.setdefault("msme_net_amount", int(order.total_amount) - fee_amount)
            meta.setdefault("fee_source", fee_source)
            order.meta = meta

        order.status = "paid"
        order.updated_at = _utcnow()
        await _emit_outbox(
            db,
            event_type="order_paid",
            payload={
                "order_id": order.id,
                "business_id": order.business_id,
                "total_amount": order.total_amount,
                "currency": order.currency,
                "transaction_fee_pct": meta.get("transaction_fee_pct"),
                "platform_fee_amount": meta.get("platform_fee_amount"),
                "msme_net_amount": meta.get("msme_net_amount"),
            },
        )
        await db.commit()
        await db.refresh(order)

        await _notify_in_app(
            user_id=order.user_id or order.user_phone,
            business_id=order.business_id,
            template="order_paid",
            payload={"order_id": order.id, "total_amount": order.total_amount, "currency": order.currency},
            correlation_id=getattr(request.state, "correlation_id", None),
        )
        await audit_client.emit_audit(
            service="order-delivery",
            event_type="order_paid",
            payload={
                "order_id": order.id,
                "business_id": order.business_id,
                "total_amount": order.total_amount,
                "currency": order.currency,
                "platform_fee_amount": meta.get("platform_fee_amount"),
                "msme_net_amount": meta.get("msme_net_amount"),
            },
            actor_id=getattr(request.state, "token_payload", {}).get("user_id") or order.user_id or order.user_phone,
            entity_type="order",
            entity_id=order.id,
            metadata={"correlation_id": getattr(request.state, "correlation_id", None)},
        )

    return OrderOut(**_serialize_order(order))


@app.post("/orders/{order_id}/initiate_payment", response_model=PaymentStatusOut)
async def order_initiate_payment(
    order_id: str,
    payload: PaymentInitiateIn,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Initiate a payment for an existing order.
    Calls payment-revenue to initiate a pawaPay deposit.
    Returns payment status from payment-revenue.
    """
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")

    if order.status != "pending_payment":
        raise HTTPException(status_code=400, detail=f"order_status_not_pending_payment: {order.status}")

    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    
    try:
        base = get_payment_revenue_base_url().rstrip("/")
        timeout = get_payment_revenue_timeout_seconds()
        
        payment_request = {
            "amount_minor": int(order.total_amount),
            "currency": order.currency,
            "phone_number": payload.phone_number,
            "provider": payload.provider,
            "order_id": order_id,
            "business_id": str(order.business_id),
            "metadata": {
                "user_phone": order.user_phone,
                "user_id": order.user_id,
                "session_id": order.session_id,
            },
        }
        
        headers = {"X-Correlation-Id": correlation_id}
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                f"{base}/pawapay/deposits/initiate",
                json=payment_request,
                headers=headers,
            )
        
        if r.status_code not in (200, 201):
            logger.error(
                "payment_revenue_error",
                extra={
                    "order_id": order_id,
                    "status_code": r.status_code,
                    "response": r.text[:500],
                    "correlation_id": correlation_id,
                },
            )
            raise HTTPException(
                status_code=r.status_code,
                detail=f"payment_revenue_failed: {r.status_code}",
            )
        
        payment_response = r.json()
        await audit_client.emit_audit(
            service="order-delivery",
            event_type="payment_initiated",
            payload={
                "order_id": order_id,
                "business_id": str(order.business_id),
                "amount_minor": int(order.total_amount),
                "currency": order.currency,
                "deposit_id": payment_response.get("external_id"),
                "payment_status": payment_response.get("status"),
            },
            actor_id=order.user_id or order.user_phone,
            entity_type="order",
            entity_id=order_id,
            metadata={"correlation_id": correlation_id},
        )
        
        return PaymentStatusOut(**payment_response)
    
    except httpx.RequestError as e:
        logger.error(
            "payment_revenue_unreachable",
            extra={
                "order_id": order_id,
                "error": str(e),
                "correlation_id": correlation_id,
            },
        )
        raise HTTPException(status_code=502, detail="payment_revenue_unreachable")


@app.post("/delivery/initiate/{order_id}", response_model=DeliveryInitiateOut)
async def delivery_initiate(
    order_id: str,
    request: Request,
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

        await _notify_in_app(
            user_id=delivery.user_id or delivery.user_phone,
            business_id=delivery.business_id,
            template="delivery_initiated",
            payload={"order_id": order.id, "delivery_id": delivery.id, "delivery_code": code, "delivery_method": delivery.delivery_method},
            correlation_id=getattr(request.state, "correlation_id", None),
        )
        await audit_client.emit_audit(
            service="order-delivery",
            event_type="delivery_initiated",
            payload={
                "delivery_id": delivery.id,
                "order_id": order.id,
                "business_id": order.business_id,
                "delivery_method": delivery.delivery_method,
                "user_phone": order.user_phone,
            },
            actor_id=delivery.user_id or delivery.user_phone,
            entity_type="delivery",
            entity_id=delivery.id,
            metadata={"correlation_id": getattr(request.state, "correlation_id", None)},
        )
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


@app.get("/deliveries/pending", response_model=list[DeliveryOut])
async def list_pending_deliveries(request: Request, business_id: str, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db_session)) -> list[DeliveryOut]:
    """List deliveries for `business_id` that are pending confirmation/delivery (for MSME dashboard)."""
    if not business_id:
        raise HTTPException(status_code=400, detail="business_id_required")
    _authorize_business_access(request, business_id)
    res = await db.execute(
        select(Delivery)
        .where(Delivery.business_id == business_id, Delivery.status != "confirmed")
        .order_by(Delivery.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = res.scalars().all()
    return [DeliveryOut(**_serialize_delivery(d)) for d in items]


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
async def delivery_confirm(delivery_id: str, payload: DeliveryConfirmIn, request: Request, db: AsyncSession = Depends(get_db_session)):
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

    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    affiliate_code = _extract_affiliate_code(order.meta)
    affiliate_id = _extract_affiliate_id(order.meta)
    occurred_at = _utcnow().isoformat().replace("+00:00", "Z")

    await _emit_outbox(
        db,
        event_type="delivery_confirmed",
        payload={"delivery_id": delivery.id, "order_id": order.id, "business_id": order.business_id},
    )
    await _emit_outbox(
        db,
        event_type="order_delivered",
        payload={
            "event_id": f"order-delivered-{order.id}",
            "event_type": "order_delivered",
            "occurred_at": occurred_at,
            "correlation_id": correlation_id,
            "order_id": order.id,
            "business_id": order.business_id,
            "affiliate_code": affiliate_code,
            "affiliate_id": affiliate_id,
        },
    )

    await db.commit()
    await db.refresh(delivery)

    await _notify_in_app(
        user_id=delivery.user_id or delivery.user_phone,
        business_id=delivery.business_id,
        template="delivery_confirmed",
        payload={"delivery_id": delivery.id, "order_id": delivery.order_id, "confirmed_by": delivery.confirmed_by},
        correlation_id=getattr(request.state, "correlation_id", None),
    )

    # Notify the business/MSME side that the customer confirmed delivery.
    await _notify_in_app(
        user_id=None,
        business_id=delivery.business_id,
        template="delivery_confirmed_business",
        payload={"delivery_id": delivery.id, "order_id": delivery.order_id, "confirmed_by": delivery.confirmed_by},
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    await audit_client.emit_audit(
        service="order-delivery",
        event_type="delivery_confirmed",
        payload={
            "delivery_id": delivery.id,
            "order_id": delivery.order_id,
            "business_id": delivery.business_id,
            "confirmed_by": delivery.confirmed_by,
        },
        actor_id=delivery.confirmed_by or delivery.user_id or delivery.user_phone,
        entity_type="delivery",
        entity_id=delivery.id,
        metadata={"correlation_id": getattr(request.state, "correlation_id", None)},
    )
    return DeliveryOut(**_serialize_delivery(delivery))


@app.post("/orders/{order_id}/confirm", response_model=OrderOut)
async def order_confirm_by_business(order_id: str, payload: dict, request: Request, db: AsyncSession = Depends(get_db_session)):
    """MSME/business side confirmation/acknowledgement of an order.

    This does not block payments. It is recorded in order metadata so dashboards can show it.
    """
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")

    _authorize_business_access(request, order.business_id)

    meta = dict(order.meta or {})
    confirmed_by = None
    if isinstance(payload, dict):
        confirmed_by = payload.get("confirmed_by")
    token_payload = getattr(request.state, "token_payload", {}) or {}
    meta["msme_confirmed_at"] = _utcnow().isoformat().replace("+00:00", "Z")
    meta["msme_confirmed_by"] = confirmed_by or token_payload.get("sub")
    order.meta = meta
    order.updated_at = _utcnow()

    await db.commit()
    await db.refresh(order)

    await _notify_in_app(
        user_id=None,
        business_id=order.business_id,
        template="order_confirmed_business",
        payload={"order_id": order.id},
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    return OrderOut(**_serialize_order(order))
