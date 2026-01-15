from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.config import (
    get_affiliate_commission_share_of_platform_fee,
    get_affiliate_engine_base_url,
    get_http_timeout_seconds,
    get_minor_unit_scale,
    get_msme_base_url,
    get_notification_base_url,
    get_notification_timeout_seconds,
    get_order_delivery_base_url,
)
from src.app.db import Base, engine, get_db_session
from src.app.idempotency import idempotent_execute, scope_for
from src.app.models import Payout, Settlement, SubscriptionPayment
from src.app.schemas import (
    PaymentSuccessIn,
    PayoutOut,
    SettlementOut,
    StatusOut,
    SubscriptionPaymentOut,
    SubscriptionPaymentSuccessIn,
)
from src.app import audit_client

app = FastAPI(title="Payment + Revenue Service (Soft Launch)")
logger = logging.getLogger("payment-revenue")

_SERVICE = "payment_revenue"
_REQ_COUNT = Counter("http_requests_total", "Total HTTP requests", ["service", "method", "route", "status"])
_REQ_LATENCY = Histogram("http_request_duration_seconds", "HTTP request duration", ["service", "method", "route"])

# Forward important Python logs (WARNING+) to audit-service.
audit_client.install_audit_log_forwarding(service=_SERVICE)


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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _round_share(amount_minor: int, share: float) -> int:
    if amount_minor <= 0 or share <= 0:
        return 0
    d = (Decimal(amount_minor) * Decimal(str(share))).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(d)


def _fee_amount_minor_units(total_minor: int, fee_bps: int) -> int:
    if total_minor <= 0 or fee_bps <= 0:
        return 0
    # Round half-up to the nearest minor unit.
    d = (Decimal(total_minor) * Decimal(fee_bps) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(d)


def _minor_to_major(amount_minor: int) -> float:
    scale = get_minor_unit_scale()
    if scale == 0:
        return float(amount_minor)
    return float(Decimal(amount_minor) / (Decimal(10) ** scale))


def _settlement_out(s: Settlement) -> dict:
    def _iso(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "id": s.id,
        "order_id": s.order_id,
        "payment_id": s.payment_id,
        "business_id": s.business_id,
        "currency": s.currency,
        "amount_minor": int(s.amount_minor),
        "fee_bps": int(s.fee_bps),
        "platform_fee_minor": int(s.platform_fee_minor),
        "affiliate_commission_minor": int(s.affiliate_commission_minor),
        "msme_net_minor": int(s.msme_net_minor),
        "status": s.status,
        "dispatched": bool(s.dispatched),
        "metadata": s.meta or {},
        "created_at": _iso(s.created_at),
        "updated_at": _iso(s.updated_at),
    }


def _payout_out(p: Payout) -> dict:
    def _iso(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "id": p.id,
        "order_id": p.order_id,
        "payment_id": p.payment_id,
        "business_id": p.business_id,
        "payee_type": p.payee_type,
        "payee_id": p.payee_id,
        "currency": p.currency,
        "amount_minor": int(p.amount_minor),
        "status": p.status,
        "metadata": p.meta or {},
        "created_at": _iso(p.created_at),
        "updated_at": _iso(p.updated_at),
    }


def _subscription_payment_out(s: SubscriptionPayment) -> dict:
    def _iso(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "id": s.id,
        "payment_id": s.payment_id,
        "business_id": s.business_id,
        "plan": s.plan,
        "paid_until": _iso(s.paid_until),
        "currency": s.currency,
        "amount_minor": int(s.amount_minor),
        "status": s.status,
        "dispatched": bool(s.dispatched),
        "metadata": s.meta or {},
        "created_at": _iso(s.created_at),
        "updated_at": _iso(s.updated_at),
    }


async def _get_fee_bps_for_business(*, business_id: str) -> tuple[int, str]:
    msme_url = get_msme_base_url().rstrip("/")
    timeout = get_http_timeout_seconds()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{msme_url}/business/{business_id}/entitlements")
    except httpx.RequestError:
        return 700, "fallback_free_msme_unreachable"

    if r.status_code != 200:
        return 700, f"fallback_free_msme_{r.status_code}"

    try:
        ent = r.json() if isinstance(r.json(), dict) else {}
    except ValueError:
        ent = {}

    pct = ent.get("transaction_fee_pct")
    try:
        fee_bps = int(round(float(pct) * 10000))
    except (TypeError, ValueError):
        fee_bps = 700

    if fee_bps not in (500, 700):
        fee_bps = 700

    return fee_bps, "msme_entitlements"


async def _dispatch_to_order_delivery(*, order_id: str, correlation_id: str) -> None:
    base = get_order_delivery_base_url().rstrip("/")
    timeout = get_http_timeout_seconds()
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{base}/orders/{order_id}/mark_paid", headers={"X-Correlation-Id": correlation_id})
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="order_delivery_mark_paid_failed")


async def _dispatch_to_affiliate_engine(*, payload: dict, correlation_id: str) -> None:
    base = get_affiliate_engine_base_url().rstrip("/")
    timeout = get_http_timeout_seconds()
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            f"{base}/events/payment-success",
            json=payload,
            headers={"X-Idempotency-Key": payload.get("event_id", ""), "X-Correlation-Id": correlation_id},
        )

    if r.status_code not in (200, 201):
        # If attribution doesn't exist, affiliate-engine returns 404; treat as recoverable failure.
        raise HTTPException(status_code=502, detail=f"affiliate_engine_payment_success_failed_{r.status_code}")


async def _dispatch_to_msme_engine_subscription(*, payload: dict, correlation_id: str) -> None:
    base = get_msme_base_url().rstrip("/")
    timeout = get_http_timeout_seconds()
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            f"{base}/events/payment_success",
            json=payload,
            headers={"X-Idempotency-Key": payload.get("event_id", ""), "X-Correlation-Id": correlation_id},
        )
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail=f"msme_engine_payment_success_failed_{r.status_code}")


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
    return response


@app.on_event("startup")
async def startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health")
async def health() -> StatusOut:
    return StatusOut(status="ok")


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/settlements/{order_id}", response_model=SettlementOut)
async def get_settlement(order_id: str, db: AsyncSession = Depends(get_db_session)):
    s = (await db.execute(select(Settlement).where(Settlement.order_id == order_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="settlement_not_found")
    return SettlementOut(**_settlement_out(s))


@app.get("/payouts/{order_id}", response_model=list[PayoutOut])
async def get_payouts(order_id: str, db: AsyncSession = Depends(get_db_session)):
    rows = (await db.execute(select(Payout).where(Payout.order_id == order_id))).scalars().all()
    return [PayoutOut(**_payout_out(p)) for p in rows]


@app.post("/events/payment-success", response_model=SettlementOut)
async def payment_success(
    request: Request,
    payload: PaymentSuccessIn,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    occurred_at = payload.occurred_at or _utcnow()

    async def _run():
        existing = (await db.execute(select(Settlement).where(Settlement.order_id == payload.order_id))).scalar_one_or_none()
        if existing:
            # If a previous attempt created the settlement but failed during dispatch,
            # retry dispatch on subsequent calls to avoid losing affiliate-engine events.
            if not bool(existing.dispatched):
                # Dispatch side effects (idempotent / safe to retry).
                await _dispatch_to_order_delivery(order_id=existing.order_id, correlation_id=correlation_id)

                payouts = (
                    await db.execute(select(Payout).where(Payout.order_id == existing.order_id).order_by(Payout.created_at.asc()))
                ).scalars().all()
                by_type = {p.payee_type: p for p in payouts}

                occurred_at_existing = existing.meta.get("occurred_at") if isinstance(existing.meta, dict) else None
                try:
                    occurred_at_iso = str(occurred_at_existing) if occurred_at_existing else _iso(existing.created_at)
                except Exception:
                    occurred_at_iso = _iso(existing.created_at)

                affiliate_event = {
                    "event_id": f"settle-{existing.id}",
                    "event_type": "payment_success",
                    "occurred_at": occurred_at_iso,
                    "correlation_id": correlation_id,
                    "producer": "payment-revenue",
                    "payment_id": existing.payment_id,
                    "order_id": existing.order_id,
                    "business_id": existing.business_id,
                    "user_phone": payload.user_phone,
                    "amount": _minor_to_major(int(existing.amount_minor)),
                    "currency": existing.currency,
                    "earnings": {
                        "msme_amount": _minor_to_major(int(existing.msme_net_minor)),
                        "affiliate_amount": _minor_to_major(int(existing.affiliate_commission_minor)),
                        "platform_amount": _minor_to_major(int(existing.platform_fee_minor) - int(existing.affiliate_commission_minor)),
                        "affiliate_id": None,
                        "affiliate_code": (existing.meta.get("affiliate_code") if isinstance(existing.meta, dict) else None),
                    },
                }

                await _dispatch_to_affiliate_engine(payload=affiliate_event, correlation_id=correlation_id)

                existing.dispatched = True
                existing.status = "dispatched"
                for p in payouts:
                    p.status = "dispatched"
                await db.commit()
                await db.refresh(existing)

            return 200, _settlement_out(existing)

        fee_bps, fee_source = await _get_fee_bps_for_business(business_id=payload.business_id)
        platform_fee = _fee_amount_minor_units(int(payload.amount_minor), fee_bps)

        share = get_affiliate_commission_share_of_platform_fee()
        affiliate_commission = _round_share(platform_fee, share)
        if affiliate_commission > platform_fee:
            affiliate_commission = platform_fee

        msme_net = int(payload.amount_minor) - platform_fee
        platform_net = platform_fee - affiliate_commission

        s = Settlement(
            order_id=payload.order_id,
            payment_id=payload.payment_id,
            business_id=payload.business_id,
            currency=payload.currency,
            amount_minor=int(payload.amount_minor),
            fee_bps=int(fee_bps),
            platform_fee_minor=int(platform_fee),
            affiliate_commission_minor=int(affiliate_commission),
            msme_net_minor=int(msme_net),
            status="computed",
            dispatched=False,
            meta={
                **(payload.metadata or {}),
                "fee_source": fee_source,
                "platform_net_minor": int(platform_net),
                "occurred_at": occurred_at.isoformat().replace("+00:00", "Z"),
            },
        )

        db.add(s)
        await db.commit()
        await db.refresh(s)

        # Create payout ledger entries (MSME + affiliate + platform).
        payout_msme = Payout(
            order_id=payload.order_id,
            payment_id=payload.payment_id,
            business_id=payload.business_id,
            payee_type="msme",
            payee_id=payload.business_id,
            currency=payload.currency,
            amount_minor=int(msme_net),
            status="pending",
            meta={"settlement_id": s.id},
        )
        payout_affiliate = Payout(
            order_id=payload.order_id,
            payment_id=payload.payment_id,
            business_id=payload.business_id,
            payee_type="affiliate",
            payee_id=None,
            currency=payload.currency,
            amount_minor=int(affiliate_commission),
            status="pending",
            meta={"settlement_id": s.id},
        )
        payout_platform = Payout(
            order_id=payload.order_id,
            payment_id=payload.payment_id,
            business_id=payload.business_id,
            payee_type="platform",
            payee_id=None,
            currency=payload.currency,
            amount_minor=int(platform_net),
            status="pending",
            meta={"settlement_id": s.id},
        )
        db.add(payout_msme)
        db.add(payout_affiliate)
        db.add(payout_platform)
        await db.commit()

        # Dispatch side effects.
        await _dispatch_to_order_delivery(order_id=payload.order_id, correlation_id=correlation_id)

        affiliate_event = {
            "event_id": f"settle-{s.id}",
            "event_type": "payment_success",
            "occurred_at": occurred_at.isoformat().replace("+00:00", "Z"),
            "correlation_id": correlation_id,
            "producer": "payment-revenue",
            "payment_id": payload.payment_id,
            "order_id": payload.order_id,
            "business_id": payload.business_id,
            "user_phone": payload.user_phone,
            # Major units for compatibility with affiliate-engine schema.
            "amount": _minor_to_major(int(payload.amount_minor)),
            "currency": payload.currency,
            "earnings": {
                "msme_amount": _minor_to_major(int(msme_net)),
                "affiliate_amount": _minor_to_major(int(affiliate_commission)),
                "platform_amount": _minor_to_major(int(platform_net)),
                "affiliate_id": None,
                "affiliate_code": (payload.metadata or {}).get("affiliate_code"),
            },
        }

        await _dispatch_to_affiliate_engine(payload=affiliate_event, correlation_id=correlation_id)

        s.dispatched = True
        s.status = "dispatched"

        payout_msme.status = "dispatched"
        payout_affiliate.status = "dispatched"
        payout_platform.status = "dispatched"

        await db.commit()
        await db.refresh(s)

        await _notify_in_app(
            user_id=payload.user_phone,
            business_id=payload.business_id,
            template="payment_settled",
            payload={
                "order_id": payload.order_id,
                "payment_id": payload.payment_id,
                "amount_minor": int(payload.amount_minor),
                "currency": payload.currency,
                "platform_fee_minor": int(platform_fee),
                "msme_net_minor": int(msme_net),
                "affiliate_commission_minor": int(affiliate_commission),
            },
            correlation_id=correlation_id,
        )
        await audit_client.emit_audit(
            service="payment-revenue",
            event_type="settlement_created",
            payload={
                "settlement_id": s.id,
                "order_id": s.order_id,
                "payment_id": s.payment_id,
                "amount_minor": int(s.amount_minor),
                "platform_fee_minor": int(platform_fee),
                "affiliate_commission_minor": int(affiliate_commission),
                "msme_net_minor": int(msme_net),
            },
            actor_id=payload.user_phone,
            entity_type="settlement",
            entity_id=s.id,
            metadata={"correlation_id": correlation_id, "business_id": payload.business_id},
        )

        return 201, _settlement_out(s)

    status, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", request.url.path),
        key=x_idempotency_key or payload.payment_id,
        run=_run,
    )
    response.status_code = int(status)
    return SettlementOut(**body)


@app.post("/events/subscription-payment-success", response_model=SubscriptionPaymentOut)
async def subscription_payment_success(
    request: Request,
    payload: SubscriptionPaymentSuccessIn,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    occurred_at = payload.occurred_at or _utcnow()
    key = x_idempotency_key or payload.payment_id

    async def _run():
        existing = (
            await db.execute(select(SubscriptionPayment).where(SubscriptionPayment.payment_id == payload.payment_id))
        ).scalar_one_or_none()
        if existing:
            return 200, _subscription_payment_out(existing)

        sub = SubscriptionPayment(
            payment_id=payload.payment_id,
            business_id=payload.business_id,
            plan=str(payload.plan),
            paid_until=payload.paid_until,
            currency=payload.currency,
            amount_minor=int(payload.amount_minor),
            status="computed",
            dispatched=False,
            meta={**(payload.metadata or {}), "occurred_at": occurred_at.isoformat().replace("+00:00", "Z")},
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)

        # Notify MSME engine to activate subscription.
        msme_event = {
            "event_id": f"sub-{sub.id}",
            "business_id": payload.business_id,
            "plan": str(payload.plan),
            "paid_until": payload.paid_until.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "amount": _minor_to_major(int(payload.amount_minor)),
            "currency": payload.currency,
            "source": "payment-revenue",
        }

        await _dispatch_to_msme_engine_subscription(payload=msme_event, correlation_id=correlation_id)

        sub.dispatched = True
        sub.status = "dispatched"
        await db.commit()
        await db.refresh(sub)

        await _notify_in_app(
            user_id=None,
            business_id=payload.business_id,
            template="subscription_paid",
            payload={
                "payment_id": payload.payment_id,
                "plan": str(payload.plan),
                "paid_until": payload.paid_until.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "amount_minor": int(payload.amount_minor),
                "currency": payload.currency,
            },
            correlation_id=correlation_id,
        )
        return 201, _subscription_payment_out(sub)

    status, body = await idempotent_execute(db=db, scope=scope_for("POST", request.url.path), key=key, run=_run)
    response.status_code = int(status)
    return SubscriptionPaymentOut(**body)
