from __future__ import annotations

import logging
import asyncio
import time
import uuid
import re
import secrets
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import httpx
import json
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
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
    get_payment_revenue_base_url,
    get_pg_schema,
    get_internal_service_secret,
    get_outbox_flush_internal_secret,
    get_outbox_flush_batch_size,
    get_outbox_flush_backoff_base_seconds,
    get_outbox_flush_backoff_max_seconds,
    get_outbox_flush_enabled,
    get_outbox_flush_interval_seconds,
    get_outbox_flush_max_attempts,
    get_pawapay_webhook_secret,
    get_pawapay_reconcile_batch_size,
    get_pawapay_reconcile_enabled,
    get_pawapay_reconcile_interval_seconds,
    get_pawapay_reconcile_stale_seconds,
    get_jwt_secret,
    get_msme_service_identifier,
    get_msme_service_password,
)
from src.app.db import Base, SessionLocal, engine, get_db_session
from src.app.idempotency import idempotent_execute, scope_for
from src.app.models import Outbox, PawaPayDeposit, PawaPayPayout, PawaPayRefund, Payout, Settlement, SubscriptionPayment
from src.app.schemas import (
    PaymentSuccessIn,
    PawaPayDepositInitiateIn,
    PawaPayPayoutInitiateIn,
    PawaPayRefundInitiateIn,
    PawaPayTxnOut,
    PayoutOut,
    RefundOut,
    RefundRequestIn,
    SettlementOut,
    StatusOut,
    SubscriptionPaymentOut,
    SubscriptionPaymentSuccessIn,
)
from src.app import audit_client
from src.app import pawapay_client
from src.app import security
from src.app.refunds import delivery_is_confirmed, utcnow_iso

app = FastAPI(title="Payment + Revenue Service (Soft Launch)")
logger = logging.getLogger("payment-revenue")

_SERVICE = "payment_revenue"
_REQ_COUNT = Counter("http_requests_total", "Total HTTP requests", ["service", "method", "route", "status"])
_REQ_LATENCY = Histogram("http_request_duration_seconds", "HTTP request duration", ["service", "method", "route"])

_AUTH_SKIP_PATHS = {
    "/health",
    "/metrics",
    "/openapi.json",
    "/docs",
    "/docs/index.html",
    "/redoc",
    # pawaPay callback URLs must not require our internal JWT.
    "/callbacks/pawapay/deposits",
    "/callbacks/pawapay/payouts",
    "/callbacks/pawapay/refunds",
}

_ZMB_PROVIDERS = {"AIRTEL_OAPI_ZMB", "MTN_MOMO_ZMB", "ZAMTEL_ZMB"}


def _normalize_zmb_phone(phone: str) -> str:
    """Normalize Zambian phone to 260XXXXXXXXX format (12 digits).
    
    Raises HTTPException if invalid.
    """
    # Strip whitespace, hyphens, spaces
    clean = "".join(c for c in str(phone).strip() if c.isdigit())
    
    # Must start with 260
    if not clean.startswith("260"):
        raise HTTPException(status_code=400, detail="phone_must_start_with_260")
    
    # Must be exactly 12 digits (260 + 9 digits)
    if len(clean) != 12:
        raise HTTPException(status_code=400, detail="phone_must_be_12_digits_260XXXXXXXXX")
    
    return clean


def _infer_zmb_provider(phone: str) -> str:
    """Infer Zambian provider from phone number.
    
    260 75/95 -> ZAMTEL_ZMB
    260 77/97 -> AIRTEL_OAPI_ZMB
    260 76/96 -> MTN_MOMO_ZMB
    
    Raises HTTPException if provider cannot be determined.
    """
    if len(phone) < 5:
        raise HTTPException(status_code=400, detail="phone_too_short_to_infer_provider")
    
    prefix = phone[0:5]  # e.g., "26075", "26095"
    
    if prefix in ("26075", "26095"):
        return "ZAMTEL_ZMB"
    elif prefix in ("26077", "26097"):
        return "AIRTEL_OAPI_ZMB"
    elif prefix in ("26076", "26096"):
        return "MTN_MOMO_ZMB"
    else:
        raise HTTPException(status_code=400, detail=f"unknown_zambian_provider_prefix_{prefix}")


def _require_pawapay_callback_secret(request: Request) -> None:
    expected = get_pawapay_webhook_secret().strip()
    if not expected:
        return
    provided = (request.headers.get("X-PawaPay-Secret") or "").strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="invalid_pawapay_callback_secret")


def _require_zmw(currency: str) -> None:
    if str(currency).upper() != "ZMW":
        raise HTTPException(status_code=400, detail="zambia_only_currency_zmw")


def _require_zmb_provider(provider: str) -> None:
    if provider not in _ZMB_PROVIDERS:
        raise HTTPException(status_code=400, detail="zambia_only_provider")

def _infer_provider_from_phone(phone: str) -> str | None:
    """Infer provider constant from a Zambian MSISDN starting with 260.

    Returns one of the provider strings from `_ZMB_PROVIDERS` or None if
    it can't be inferred.
    """
    if not phone or not phone.isdigit() or not phone.startswith("260"):
        return None
    # Expect MSISDN like 260XXXXXXXXX (12 digits: 260 + 9 digits)
    if len(phone) != 12:
        return None
    prefix5 = phone[:5]
    if prefix5 in ("26075", "26095"):
        return "ZAMTEL_ZMB"
    if prefix5 in ("26077", "26097"):
        return "AIRTEL_OAPI_ZMB"
    if prefix5 in ("26076", "26096"):
        return "MTN_MOMO_ZMB"
    return None


def _validate_and_infer_zmb_phone_and_provider(phone: str | None, provider: str | None) -> tuple[str, str]:
    """Validate Zambian phone MSISDN and return (phone, provider).

    - Ensures phone is digits, starts with `260` and has length 12.
    - Infers provider from phone when provider is missing.
    - If provider is provided, ensures it matches the inferred provider when possible.
    Raises HTTPException on invalid input.
    """
    if not phone:
        raise HTTPException(status_code=400, detail="missing_phoneNumber")
    p = str(phone).strip()
    if not p.isdigit() or not p.startswith("260") or len(p) != 12:
        raise HTTPException(status_code=400, detail="invalid_zambian_phone")

    inferred = _infer_provider_from_phone(p)
    if provider:
        prov = str(provider)
        # If we can infer and it conflicts, reject.
        if inferred and prov not in (inferred,):
            raise HTTPException(status_code=400, detail="provider_mismatch_with_phone")
        if prov not in _ZMB_PROVIDERS:
            raise HTTPException(status_code=400, detail="zambia_only_provider")
        return p, prov

    if not inferred:
        raise HTTPException(status_code=400, detail="unable_to_infer_provider_from_phone")
    return p, inferred


def _minor_to_pawapay_amount(amount_minor: int) -> str:
    scale = get_minor_unit_scale()
    if scale <= 0:
        return str(int(amount_minor))

    q = Decimal("1") / (Decimal(10) ** scale)
    d = (Decimal(int(amount_minor)) / (Decimal(10) ** scale)).quantize(q, rounding=ROUND_HALF_UP)
    # Always send plain decimal string.
    return format(d, "f")


def _pawapay_amount_to_minor(amount: str | None) -> int:
    if not amount:
        return 0
    scale = get_minor_unit_scale()
    try:
        d = Decimal(str(amount))
    except Exception:
        return 0
    if scale <= 0:
        return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return int((d * (Decimal(10) ** scale)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _extract_failure(body: dict) -> tuple[str | None, str | None]:
    fr = body.get("failureReason") if isinstance(body.get("failureReason"), dict) else None
    if fr:
        code = fr.get("failureCode") or fr.get("code")
        msg = fr.get("failureMessage") or fr.get("message")
        return (str(code) if code else None, str(msg) if msg else None)

    rr = body.get("rejectionReason") if isinstance(body.get("rejectionReason"), dict) else None
    if rr:
        code = rr.get("rejectionCode") or rr.get("code")
        msg = rr.get("rejectionMessage") or rr.get("message")
        return (str(code) if code else None, str(msg) if msg else None)

    return (None, None)


_PAWAPAY_TERMINAL = {"COMPLETED", "FAILED", "REJECTED"}


async def _reconcile_pawapay_once(*, db: AsyncSession, correlation_id: str) -> dict:
    """Check pawaPay status for old pending rows and update local DB.

    This protects us when callbacks were not delivered.
    """
    stale_seconds = get_pawapay_reconcile_stale_seconds()
    batch_size = get_pawapay_reconcile_batch_size()
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_seconds)

    updated = 0
    checked = 0
    errors = 0

    async def _update_deposit(row: PawaPayDeposit) -> None:
        nonlocal updated, checked, errors
        checked += 1
        try:
            r = await pawapay_client.get_deposit_status(deposit_id=row.deposit_id, correlation_id=correlation_id)
        except Exception:
            errors += 1
            return

        status = str(r.body.get("status") or row.status)
        amount_minor = _pawapay_amount_to_minor(r.body.get("amount"))
        currency = str(r.body.get("currency") or row.currency or "ZMW").upper()
        failure_code, failure_message = _extract_failure(r.body)

        changed = False
        if status and status != row.status:
            row.status = status
            changed = True
        if amount_minor and int(amount_minor) != int(row.amount_minor or 0):
            row.amount_minor = int(amount_minor)
            changed = True
        if currency and currency != row.currency:
            row.currency = currency
            changed = True
        if failure_code != row.failure_code or failure_message != row.failure_message:
            row.failure_code = failure_code
            row.failure_message = failure_message
            changed = True

        row.meta = {**(row.meta or {}), "status_check": r.body, "status_check_code": r.status_code}
        row.updated_at = _utcnow()
        if changed:
            updated += 1

    async def _update_payout(row: PawaPayPayout) -> None:
        nonlocal updated, checked, errors
        checked += 1
        try:
            r = await pawapay_client.get_payout_status(payout_id=row.payout_id, correlation_id=correlation_id)
        except Exception:
            errors += 1
            return

        status = str(r.body.get("status") or row.status)
        amount_minor = _pawapay_amount_to_minor(r.body.get("amount"))
        currency = str(r.body.get("currency") or row.currency or "ZMW").upper()
        failure_code, failure_message = _extract_failure(r.body)

        changed = False
        if status and status != row.status:
            row.status = status
            changed = True
        if amount_minor and int(amount_minor) != int(row.amount_minor or 0):
            row.amount_minor = int(amount_minor)
            changed = True
        if currency and currency != row.currency:
            row.currency = currency
            changed = True
        if failure_code != row.failure_code or failure_message != row.failure_message:
            row.failure_code = failure_code
            row.failure_message = failure_message
            changed = True

        row.meta = {**(row.meta or {}), "status_check": r.body, "status_check_code": r.status_code}
        row.updated_at = _utcnow()
        if changed:
            updated += 1

    async def _update_refund(row: PawaPayRefund) -> None:
        nonlocal updated, checked, errors
        checked += 1
        try:
            r = await pawapay_client.get_refund_status(refund_id=row.refund_id, correlation_id=correlation_id)
        except Exception:
            errors += 1
            return

        status = str(r.body.get("status") or row.status)
        amount_minor = _pawapay_amount_to_minor(r.body.get("amount"))
        currency = str(r.body.get("currency") or row.currency or "ZMW").upper()
        failure_code, failure_message = _extract_failure(r.body)

        changed = False
        if status and status != row.status:
            row.status = status
            changed = True
        if amount_minor and int(amount_minor) != int(row.amount_minor or 0):
            row.amount_minor = int(amount_minor)
            changed = True
        if currency and currency != row.currency:
            row.currency = currency
            changed = True
        if failure_code != row.failure_code or failure_message != row.failure_message:
            row.failure_code = failure_code
            row.failure_message = failure_message
            changed = True

        row.meta = {**(row.meta or {}), "status_check": r.body, "status_check_code": r.status_code}
        row.updated_at = _utcnow()
        if changed:
            updated += 1

    dep_rows = (
        await db.execute(
            select(PawaPayDeposit)
            .where(PawaPayDeposit.updated_at <= cutoff)
            .where(~PawaPayDeposit.status.in_(_PAWAPAY_TERMINAL))
            .order_by(PawaPayDeposit.updated_at.asc())
            .limit(batch_size)
        )
    ).scalars().all()

    pay_rows = (
        await db.execute(
            select(PawaPayPayout)
            .where(PawaPayPayout.updated_at <= cutoff)
            .where(~PawaPayPayout.status.in_(_PAWAPAY_TERMINAL))
            .order_by(PawaPayPayout.updated_at.asc())
            .limit(batch_size)
        )
    ).scalars().all()

    ref_rows = (
        await db.execute(
            select(PawaPayRefund)
            .where(PawaPayRefund.updated_at <= cutoff)
            .where(~PawaPayRefund.status.in_(_PAWAPAY_TERMINAL))
            .order_by(PawaPayRefund.updated_at.asc())
            .limit(batch_size)
        )
    ).scalars().all()

    for row in dep_rows:
        await _update_deposit(row)
    for row in pay_rows:
        await _update_payout(row)
    for row in ref_rows:
        await _update_refund(row)

    await db.commit()
    return {"checked": checked, "updated": updated, "errors": errors, "stale_seconds": stale_seconds}


async def _reconcile_loop() -> None:
    # Runs forever (if enabled), sleeping between iterations.
    while True:
        try:
            async with SessionLocal() as session:
                await _reconcile_pawapay_once(db=session, correlation_id=str(uuid.uuid4()))
        except Exception:
            logger.exception("pawapay_reconcile_failed")

        await asyncio.sleep(get_pawapay_reconcile_interval_seconds())


async def _flush_outbox_once(*, db: AsyncSession, correlation_id: str) -> dict:
    max_attempts = get_outbox_flush_max_attempts()
    now = datetime.now(timezone.utc)
    batch_size = get_outbox_flush_batch_size()

    rows = (
        await db.execute(
            select(Outbox)
            .where(Outbox.status == "pending")
            .where((Outbox.send_after == None) | (Outbox.send_after <= now))
            .order_by(Outbox.created_at.asc())
            .limit(batch_size)
        )
    ).scalars().all()

    results = {"sent": 0, "failed": 0}

    def _schedule_retry(row: Outbox) -> None:
        row.attempts = int(row.attempts or 0) + 1
        base = get_outbox_flush_backoff_base_seconds()
        max_backoff = get_outbox_flush_backoff_max_seconds()
        backoff = min(base * (2 ** max(0, row.attempts - 1)), max_backoff)
        row.send_after = datetime.now(timezone.utc) + timedelta(seconds=backoff)

    def _should_mark_failed_http(status_code: int) -> bool:
        
        # Treat most 4xx as permanent; keep retrying 408/429.
        
        return 400 <= status_code < 500 and status_code not in (408, 429)
    async with httpx.AsyncClient(timeout=get_http_timeout_seconds()) as client:
        for row in rows:
            try:
                headers = {"X-Correlation-Id": correlation_id}
                # Attach service JWT when available so downstreams requiring auth accept requests.
                token = await _get_bearer_token()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                r = await client.post(row.destination, json=row.payload, headers=headers)
                if r.status_code in (200, 201):
                    row.status = "sent"
                    row.last_error = None
                    results["sent"] += 1
                else:
                    row.last_error = f"http_{r.status_code}"
                    if _should_mark_failed_http(r.status_code):
                        row.attempts = int(row.attempts or 0) + 1
                        row.status = "failed"
                        results["failed"] += 1
                    elif max_attempts > 0 and (int(row.attempts or 0) + 1) >= max_attempts:
                        row.attempts = int(row.attempts or 0) + 1
                        row.status = "failed"
                        results["failed"] += 1
                    else:
                        _schedule_retry(row)
                row.updated_at = _utcnow()
                await db.commit()
            except Exception as exc:
                row.last_error = str(exc)
                if max_attempts > 0 and (int(row.attempts or 0) + 1) >= max_attempts:
                    row.attempts = int(row.attempts or 0) + 1
                    row.status = "failed"
                    results["failed"] += 1
                else:
                    _schedule_retry(row)
                row.updated_at = _utcnow()
                await db.commit()

    return results


async def _outbox_flush_loop() -> None:
    while True:
        try:
            async with SessionLocal() as session:
                await _flush_outbox_once(db=session, correlation_id=str(uuid.uuid4()))
        except Exception:
            logger.exception("outbox_flush_failed")

        await asyncio.sleep(get_outbox_flush_interval_seconds())


@app.post("/jobs/pawapay/reconcile")
async def pawapay_reconcile_now(request: Request, db: AsyncSession = Depends(get_db_session)):
    """Manual trigger for reconciliation.

    Use this from a scheduler (cron/K8s CronJob) if you don't want the built-in loop.
    """
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    return await _reconcile_pawapay_once(db=db, correlation_id=correlation_id)


@app.post("/jobs/outbox/flush")
async def outbox_flush_now(request: Request, db: AsyncSession = Depends(get_db_session)):
    """Flush pending outbox events to their destinations.

    This is a simple best-effort flusher. It marks rows as `sent` on success and
    retries with backoff on transient failures.
    """
    correlation_id = request.headers.get("X-Correlation-Id") or getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    results = await _flush_outbox_once(db=db, correlation_id=correlation_id)
    return {"ok": True, "results": results}


async def _ensure_postgres_outbox_schema(conn) -> None:
    # Best-effort: keep production DB in sync when we add new columns used for idempotency.
    # (We still keep create_all for fresh setups.)
    if not engine.dialect.name.startswith("postgres"):
        return
    schema = get_pg_schema() or "public"
    await conn.execute(text(f'ALTER TABLE IF EXISTS "{schema}".outbox ADD COLUMN IF NOT EXISTS dedupe_key varchar(128)'))
    await conn.execute(text(f'CREATE UNIQUE INDEX IF NOT EXISTS uq_outbox_topic_dedupe_key ON "{schema}".outbox (topic, dedupe_key)'))


def _txn_out(*, external_id: str, status: str, amount_minor: int, currency: str, provider: str | None, phone_number: str | None, meta: dict | None) -> PawaPayTxnOut:
    return PawaPayTxnOut(
        external_id=str(external_id),
        status=str(status),
        amount_minor=int(amount_minor or 0),
        currency=str(currency or "ZMW"),
        provider=provider,
        phone_number=phone_number,
        metadata=(meta or {}),
    )

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


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Require Bearer access tokens issued by msme-engine for all routes except health/metrics/docs.
    if request.url.path in _AUTH_SKIP_PATHS:
        return await call_next(request)

    try:
        await security.require_access_token(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


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


# ----- Bearer token helper -----
_cached_token: str | None = None
_cached_token_exp: int | None = None
_token_lock = asyncio.Lock()


async def _get_bearer_token() -> str | None:
    global _cached_token, _cached_token_exp
    now_ts = int(datetime.now(timezone.utc).timestamp())
    if _cached_token and _cached_token_exp and _cached_token_exp - 10 > now_ts:
        return _cached_token

    async with _token_lock:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if _cached_token and _cached_token_exp and _cached_token_exp - 10 > now_ts:
            return _cached_token

        identifier = get_msme_service_identifier()
        password = get_msme_service_password()
        if not identifier or not password:
            return None

        msme = get_msme_base_url().rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=get_http_timeout_seconds()) as client:
                r = await client.post(f"{msme}/auth/login", json={"identifier": identifier, "password": password})
        except Exception:
            return None

        if r.status_code != 200:
            return None

        body = {}
        try:
            body = r.json()
        except Exception:
            pass
        access = body.get("access_token") or body.get("accessToken") or None
        if not access:
            return None

        try:
            payload = security.jwt_decode(access, secret=get_jwt_secret())
            exp = int(payload.get("exp") or 0)
        except Exception:
            exp = None

        _cached_token = access
        _cached_token_exp = exp
        return _cached_token


async def _dispatch_to_order_delivery(*, order_id: str, correlation_id: str) -> None:
    base = get_order_delivery_base_url().rstrip("/")
    timeout = get_http_timeout_seconds()
    headers = {"X-Correlation-Id": correlation_id}
    token = await _get_bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{base}/orders/{order_id}/mark_paid", headers=headers)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="order_delivery_mark_paid_failed")


def _build_affiliate_event(*, event_id: str, correlation_id: str, payment_id: str | None, order_id: str | None, business_id: str, user_phone: str | None, amount_minor: int, currency: str, msme_amount_minor: int, affiliate_amount_minor: int, platform_amount_minor: int, affiliate_id: str | None = None, affiliate_code: str | None = None, occurred_at: datetime | str | None = None) -> dict:
    # Normalize occurred_at to ISO Z string
    if occurred_at is None:
        occurred_iso = _utcnow().isoformat().replace("+00:00", "Z")
    elif isinstance(occurred_at, datetime):
        occurred_iso = occurred_at.isoformat().replace("+00:00", "Z")
    else:
        occurred_iso = str(occurred_at)

    return {
        "event_id": event_id,
        "event_type": "payment_success",
        "occurred_at": occurred_iso,
        "correlation_id": correlation_id,
        "producer": "payment-revenue",
        "payment_id": payment_id,
        "order_id": order_id,
        "business_id": business_id,
        "user_phone": user_phone,
        "amount": _minor_to_major(int(amount_minor or 0)),
        "currency": currency,
        "earnings": {
            "msme_amount": _minor_to_major(int(msme_amount_minor or 0)),
            "affiliate_amount": _minor_to_major(int(affiliate_amount_minor or 0)),
            "platform_amount": _minor_to_major(int(platform_amount_minor or 0)),
            "affiliate_id": affiliate_id,
            "affiliate_code": affiliate_code,
        },
    }


async def _dispatch_to_affiliate_engine(*, payload: dict, correlation_id: str) -> None:
    base = get_affiliate_engine_base_url().rstrip("/")
    timeout = get_http_timeout_seconds()
    headers = {"X-Idempotency-Key": payload.get("event_id", ""), "X-Correlation-Id": correlation_id}
    token = await _get_bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{base}/events/payment-success", json=payload, headers=headers)

    if r.status_code not in (200, 201):
        # If attribution doesn't exist, affiliate-engine returns 404; treat as recoverable failure.
        raise HTTPException(status_code=502, detail=f"affiliate_engine_payment_success_failed_{r.status_code}")


async def _dispatch_to_msme_engine_subscription(*, payload: dict, correlation_id: str) -> None:
    base = get_msme_base_url().rstrip("/")
    timeout = get_http_timeout_seconds()
    headers = {"X-Idempotency-Key": payload.get("event_id", ""), "X-Correlation-Id": correlation_id}
    token = await _get_bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{base}/events/payment_success", json=payload, headers=headers)
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


async def startup() -> None:
    async with engine.begin() as conn:
        schema = get_pg_schema()
        if schema and engine.dialect.name.startswith("postgres"):
            # Allow only letters, numbers, underscore to avoid SQL injection.
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
                raise RuntimeError("invalid_pg_schema")
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await _ensure_postgres_outbox_schema(conn)
        await conn.run_sync(Base.metadata.create_all)

    # Optional: run reconciliation loop inside the service.
    # If you already use an external scheduler (cron/K8s CronJob), keep this off.
    if get_pawapay_reconcile_enabled():
        asyncio.create_task(_reconcile_loop())

    if get_outbox_flush_enabled():
        asyncio.create_task(_outbox_flush_loop())


# Register startup handler without using the deprecated decorator.
app.add_event_handler("startup", startup)


@app.get("/health")
async def health() -> StatusOut:
    return StatusOut(status="ok")


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/refunds/request", response_model=RefundOut)
async def request_refund(
    request: Request,
    payload: RefundRequestIn,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    """Request a refund for an order.

    Policy: allowed only if the payment exists AND delivery is NOT confirmed.
    """
    correlation_id = request.headers.get("X-Correlation-Id") or getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    authorization = request.headers.get("Authorization")

    async def _run():
        settlement = (
            await db.execute(select(Settlement).where(Settlement.order_id == payload.order_id))
        ).scalar_one_or_none()
        if not settlement:
            raise HTTPException(status_code=404, detail="settlement_not_found")

        _authorize_business_access(request, settlement.business_id)

        try:
            confirmed = await delivery_is_confirmed(order_id=payload.order_id, authorization=authorization, correlation_id=correlation_id)
        except httpx.HTTPStatusError:
            raise HTTPException(status_code=502, detail="order_delivery_lookup_failed")

        if confirmed:
            raise HTTPException(status_code=409, detail="refund_not_allowed_delivery_confirmed")

        meta = dict(settlement.meta or {})
        if meta.get("refund_requested") is True:
            return 200, {
                "status": "refund_already_requested",
                "order_id": settlement.order_id,
                "business_id": settlement.business_id,
                "metadata": meta,
            }

        meta["refund_requested"] = True
        meta["refund_requested_at"] = utcnow_iso()
        if payload.reason:
            meta["refund_reason"] = payload.reason
        settlement.meta = meta
        settlement.updated_at = _utcnow()
        settlement.status = "refund_requested"

        await db.commit()
        await db.refresh(settlement)

        await _notify_in_app(
            user_id=None,
            business_id=settlement.business_id,
            template="refund_requested_business",
            payload={"order_id": settlement.order_id, "reason": payload.reason},
            correlation_id=correlation_id,
        )

        token_payload = getattr(request.state, "token_payload", {}) or {}
        await _notify_in_app(
            user_id=str(token_payload.get("sub")) if token_payload.get("sub") else None,
            business_id=settlement.business_id,
            template="refund_requested",
            payload={"order_id": settlement.order_id},
            correlation_id=correlation_id,
        )

        return 201, {
            "status": "refund_requested",
            "order_id": settlement.order_id,
            "business_id": settlement.business_id,
            "metadata": settlement.meta or {},
        }

    status, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", "/refunds/request"),
        key=x_idempotency_key,
        run=_run,
    )
    response.status_code = int(status)
    return RefundOut(**body)


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


# -----------------
# pawaPay (Zambia)
# -----------------


@app.post("/pawapay/deposits/initiate", response_model=PawaPayTxnOut)
async def pawapay_initiate_deposit(
    request: Request,
    payload: PawaPayDepositInitiateIn,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())

    _require_zmw(payload.currency)
    
    # Normalize phone and infer provider
    normalized_phone = _normalize_zmb_phone(payload.phone_number)
    provider = payload.provider or _infer_zmb_provider(normalized_phone)
    _require_zmb_provider(provider)

    deposit_id = payload.deposit_id or str(uuid.uuid4())
    key = x_idempotency_key or deposit_id

    async def _run():
        existing = (await db.execute(select(PawaPayDeposit).where(PawaPayDeposit.deposit_id == deposit_id))).scalar_one_or_none()
        if existing:
            return 200, _txn_out(
                external_id=existing.deposit_id,
                status=existing.status,
                amount_minor=int(existing.amount_minor or 0),
                currency=existing.currency,
                provider=existing.provider,
                phone_number=existing.phone_number,
                meta=existing.meta,
            ).model_dump(mode="json")

        # Record who initiated this deposit so callbacks can reply only to that
        # initiating service instead of broadcasting to multiple consumers.
        token_payload = getattr(request.state, "token_payload", {}) or {}
        initiator_id = token_payload.get("sub") or token_payload.get("service") or token_payload.get("iss")
        initiator_role = token_payload.get("role")
        row = PawaPayDeposit(
            deposit_id=deposit_id,
            order_id=payload.order_id,
            business_id=payload.business_id,
            currency=str(payload.currency).upper(),
            amount_minor=int(payload.amount_minor),
            phone_number=normalized_phone,
            provider=provider,
            status="CREATED",
            meta={
                "request": payload.model_dump(mode="json"),
                "correlation_id": correlation_id,
                **(payload.metadata or {}),
                "initiator_id": initiator_id,
                "initiator_role": initiator_role,
            },
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)

        try:
            pr = await pawapay_client.initiate_deposit(
                deposit_id=deposit_id,
                amount=_minor_to_pawapay_amount(int(payload.amount_minor)),
                currency=str(payload.currency).upper(),
                phone_number=normalized_phone,
                provider=provider,
                correlation_id=correlation_id,
            )
        except ValueError:
            raise HTTPException(status_code=500, detail="pawapay_config_missing")
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="pawapay_unreachable")

        row.status = str(pr.body.get("status") or f"HTTP_{pr.status_code}")
        row.meta = {**(row.meta or {}), "pawapay_response": pr.body, "pawapay_status_code": pr.status_code}
        row.updated_at = _utcnow()
        await db.commit()
        await db.refresh(row)

        return 201, _txn_out(
            external_id=row.deposit_id,
            status=row.status,
            amount_minor=int(row.amount_minor or 0),
            currency=row.currency,
            provider=row.provider,
            phone_number=row.phone_number,
            meta=row.meta,
        ).model_dump(mode="json")

    status, body = await idempotent_execute(db=db, scope=scope_for("POST", request.url.path), key=key, run=_run)
    response.status_code = int(status)
    return PawaPayTxnOut(**body)


@app.post("/pawapay/payouts/initiate", response_model=PawaPayTxnOut)
async def pawapay_initiate_payout(
    request: Request,
    payload: PawaPayPayoutInitiateIn,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())

    _require_zmw(payload.currency)
    
    # Normalize phone and infer provider
    normalized_phone = _normalize_zmb_phone(payload.phone_number)
    provider = payload.provider or _infer_zmb_provider(normalized_phone)
    _require_zmb_provider(provider)

    payout_id = payload.payout_id or str(uuid.uuid4())
    key = x_idempotency_key or payout_id

    async def _run():
        existing = (await db.execute(select(PawaPayPayout).where(PawaPayPayout.payout_id == payout_id))).scalar_one_or_none()
        if existing:
            return 200, _txn_out(
                external_id=existing.payout_id,
                status=existing.status,
                amount_minor=int(existing.amount_minor or 0),
                currency=existing.currency,
                provider=existing.provider,
                phone_number=existing.phone_number,
                meta=existing.meta,
            ).model_dump(mode="json")

        row = PawaPayPayout(
            payout_id=payout_id,
            order_id=payload.order_id,
            business_id=payload.business_id,
            currency=str(payload.currency).upper(),
            amount_minor=int(payload.amount_minor),
            phone_number=normalized_phone,
            provider=provider,
            status="CREATED",
            meta={"request": payload.model_dump(mode="json"), "correlation_id": correlation_id, **(payload.metadata or {})},
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)

        try:
            pr = await pawapay_client.initiate_payout(
                payout_id=payout_id,
                amount=_minor_to_pawapay_amount(int(payload.amount_minor)),
                currency=str(payload.currency).upper(),
                phone_number=normalized_phone,
                provider=provider,
                correlation_id=correlation_id,
            )
        except ValueError:
            raise HTTPException(status_code=500, detail="pawapay_config_missing")
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="pawapay_unreachable")

        row.status = str(pr.body.get("status") or f"HTTP_{pr.status_code}")
        row.meta = {**(row.meta or {}), "pawapay_response": pr.body, "pawapay_status_code": pr.status_code}
        row.updated_at = _utcnow()
        await db.commit()
        await db.refresh(row)

        return 201, _txn_out(
            external_id=row.payout_id,
            status=row.status,
            amount_minor=int(row.amount_minor or 0),
            currency=row.currency,
            provider=row.provider,
            phone_number=row.phone_number,
            meta=row.meta,
        ).model_dump(mode="json")

    status, body = await idempotent_execute(db=db, scope=scope_for("POST", request.url.path), key=key, run=_run)
    response.status_code = int(status)
    return PawaPayTxnOut(**body)


@app.post("/pawapay/refunds/initiate", response_model=PawaPayTxnOut)
async def pawapay_initiate_refund(
    request: Request,
    payload: PawaPayRefundInitiateIn,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())

    currency = (payload.currency or "ZMW")
    _require_zmw(currency)

    refund_id = payload.refund_id or str(uuid.uuid4())
    key = x_idempotency_key or refund_id

    async def _run():
        existing = (await db.execute(select(PawaPayRefund).where(PawaPayRefund.refund_id == refund_id))).scalar_one_or_none()
        if existing:
            return 200, _txn_out(
                external_id=existing.refund_id,
                status=existing.status,
                amount_minor=int(existing.amount_minor or 0),
                currency=existing.currency,
                provider=None,
                phone_number=None,
                meta=existing.meta,
            ).model_dump(mode="json")

        row = PawaPayRefund(
            refund_id=refund_id,
            deposit_id=payload.deposit_id,
            order_id=payload.order_id,
            business_id=payload.business_id,
            currency=str(currency).upper(),
            amount_minor=int(payload.amount_minor or 0),
            status="CREATED",
            meta={"request": payload.model_dump(mode="json"), "correlation_id": correlation_id, **(payload.metadata or {})},
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)

        amount = _minor_to_pawapay_amount(int(payload.amount_minor)) if payload.amount_minor is not None else None

        try:
            # pawaPay requires `currency` parameter even for full refunds (when amount is omitted),
            # so always send currency.
            pr = await pawapay_client.initiate_refund(
                refund_id=refund_id,
                deposit_id=payload.deposit_id,
                amount=amount,
                currency=str(currency).upper(),
                correlation_id=correlation_id,
            )
        except ValueError:
            raise HTTPException(status_code=500, detail="pawapay_config_missing")
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="pawapay_unreachable")

        row.status = str(pr.body.get("status") or f"HTTP_{pr.status_code}")
        row.meta = {**(row.meta or {}), "pawapay_response": pr.body, "pawapay_status_code": pr.status_code}
        row.updated_at = _utcnow()
        await db.commit()
        await db.refresh(row)

        return 201, _txn_out(
            external_id=row.refund_id,
            status=row.status,
            amount_minor=int(row.amount_minor or 0),
            currency=row.currency,
            provider=None,
            phone_number=None,
            meta=row.meta,
        ).model_dump(mode="json")

    status, body = await idempotent_execute(db=db, scope=scope_for("POST", request.url.path), key=key, run=_run)
    response.status_code = int(status)
    return PawaPayTxnOut(**body)


@app.get("/pawapay/deposits/{deposit_id}", response_model=PawaPayTxnOut)
async def pawapay_get_deposit(deposit_id: str, db: AsyncSession = Depends(get_db_session)):
    row = (await db.execute(select(PawaPayDeposit).where(PawaPayDeposit.deposit_id == deposit_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="pawapay_deposit_not_found")
    return _txn_out(
        external_id=row.deposit_id,
        status=row.status,
        amount_minor=int(row.amount_minor or 0),
        currency=row.currency,
        provider=row.provider,
        phone_number=row.phone_number,
        meta=row.meta,
    )


@app.get("/pawapay/payouts/{payout_id}", response_model=PawaPayTxnOut)
async def pawapay_get_payout(payout_id: str, db: AsyncSession = Depends(get_db_session)):
    row = (await db.execute(select(PawaPayPayout).where(PawaPayPayout.payout_id == payout_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="pawapay_payout_not_found")
    return _txn_out(
        external_id=row.payout_id,
        status=row.status,
        amount_minor=int(row.amount_minor or 0),
        currency=row.currency,
        provider=row.provider,
        phone_number=row.phone_number,
        meta=row.meta,
    )


@app.get("/pawapay/refunds/{refund_id}", response_model=PawaPayTxnOut)
async def pawapay_get_refund(refund_id: str, db: AsyncSession = Depends(get_db_session)):
    row = (await db.execute(select(PawaPayRefund).where(PawaPayRefund.refund_id == refund_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="pawapay_refund_not_found")
    return _txn_out(
        external_id=row.refund_id,
        status=row.status,
        amount_minor=int(row.amount_minor or 0),
        currency=row.currency,
        provider=None,
        phone_number=None,
        meta=row.meta,
    )


@app.post("/callbacks/pawapay/deposits")
async def pawapay_deposit_callback(request: Request, db: AsyncSession = Depends(get_db_session)):
    _require_pawapay_callback_secret(request)
    raw = await request.body()
    if not raw or raw.strip() == b"":
        logger.error("empty_pawapay_callback_body", extra={"path": request.url.path})
        return JSONResponse(status_code=400, content={"detail": "empty_body"})
    try:
        body = json.loads(raw)
    except Exception:
        logger.error("malformed_pawapay_callback_json", extra={"path": request.url.path, "raw": raw.decode("utf-8", errors="replace")})
        return JSONResponse(status_code=400, content={"detail": "malformed_json"})
    deposit_id = str(body.get("depositId") or "").strip()
    if not deposit_id:
        raise HTTPException(status_code=400, detail="missing_depositId")

    payer = body.get("payer") if isinstance(body.get("payer"), dict) else {}
    acct = payer.get("accountDetails") if isinstance(payer.get("accountDetails"), dict) else {}
    phone = acct.get("phoneNumber")
    provider = acct.get("provider")

    status = str(body.get("status") or "UNKNOWN")
    amount_minor = _pawapay_amount_to_minor(body.get("amount"))
    currency = str(body.get("currency") or "ZMW").upper()
    failure_code, failure_message = _extract_failure(body)

    row = (await db.execute(select(PawaPayDeposit).where(PawaPayDeposit.deposit_id == deposit_id))).scalar_one_or_none()
    if not row:
        row = PawaPayDeposit(
            deposit_id=deposit_id,
            currency=currency,
            amount_minor=amount_minor,
            phone_number=str(phone) if phone else None,
            provider=str(provider) if provider else None,
            status=status,
            failure_code=failure_code,
            failure_message=failure_message,
            meta={"callback": body},
        )
        db.add(row)
    else:
        row.status = status
        if amount_minor:
            row.amount_minor = int(amount_minor)
        row.currency = currency
        row.phone_number = str(phone) if phone else row.phone_number
        row.provider = str(provider) if provider else row.provider
        row.failure_code = failure_code
        row.failure_message = failure_message
        row.meta = {**(row.meta or {}), "callback": body}
        row.updated_at = _utcnow()

    # Always persist the callback update quickly, even if outbox insert is a duplicate.
    await db.commit()

    if status in _PAWAPAY_TERMINAL:
        correlation_id = getattr(request.state, "correlation_id", None) or request.headers.get("X-Correlation-Id") or str(uuid.uuid4())

        internal_secret = (get_outbox_flush_internal_secret() or "").strip()

        # 1) Enqueue canonical outbox events for terminal statuses so downstream
        # services (settlement, affiliate, notification, analytics) receive
        # both successes and failures asynchronously.
        # Do not enqueue internal self-targeted events to Payment-Revenue's own
        # `/events/*` endpoints. The initiating service owns handling the
        # callback (or may poll); payment-revenue will not create a base_self
        # `payment_success`/`payment_failed` outbox here to avoid duplicate
        # internal dispatch. Notification outbox (below) still applies.

        payload_event = {
            "event_id": f"deposit-{deposit_id}",
            "event_type": "pawapay_deposit",
            "occurred_at": _utcnow().isoformat().replace("+00:00", "Z"),
            "correlation_id": correlation_id,
            "producer": "payment-revenue",
            "deposit_id": deposit_id,
            "status": status,
            "amount": _minor_to_major(int(amount_minor or 0)),
            "currency": currency,
            "phone_number": row.phone_number,
            "provider": row.provider,
            "meta": row.meta or {},
        }

        # Enqueue canonical outbox events directly to downstream services
        # (msme-engine, affiliate-engine, order-delivery). We intentionally do
        # not enqueue to this service's own `/events/*` endpoints to avoid
        # duplicate internal dispatch — the initiating service should handle
        # any synchronous response logic.
        # Determine the recorded initiator and map to a single downstream base URL.
        initiator_id = (row.meta or {}).get("initiator_id") or (row.meta or {}).get("initiator")
        initiator_role = (row.meta or {}).get("initiator_role")

        # Heuristic mapping: prefer msme-engine when initiator matches our configured
        # service identifier; otherwise try to detect affiliate/order by name.
        target_base = None
        if initiator_id and str(initiator_id) == str(get_msme_service_identifier()):
            try:
                target_base = get_msme_base_url().rstrip("/")
            except Exception:
                target_base = None
        elif initiator_id and ("affiliate" in str(initiator_id).lower() or "affiliat" in str(initiator_id).lower()):
            try:
                target_base = get_affiliate_engine_base_url().rstrip("/")
            except Exception:
                target_base = None
        elif initiator_id and ("order" in str(initiator_id).lower() or "delivery" in str(initiator_id).lower()):
            try:
                target_base = get_order_delivery_base_url().rstrip("/")
            except Exception:
                target_base = None
        else:
            # Fallback: if we have an order_id assume msme-engine (most common).
            try:
                if row.order_id:
                    target_base = get_msme_base_url().rstrip("/")
            except Exception:
                target_base = None

        occurred_at_iso = payload_event.get("occurred_at")

        if not target_base:
            # No clear initiator — do not broadcast; only create notification outbox (already handled).
            target_base = None

        if target_base:
            if status == "COMPLETED":
                # Build a minimal success event for the initiator.
                initiator_event = {
                    "event_id": f"deposit-{deposit_id}",
                    "event_type": "payment_success",
                    "occurred_at": occurred_at_iso,
                    "correlation_id": correlation_id,
                    "producer": "payment-revenue",
                    "payment_id": deposit_id,
                    "order_id": str(row.order_id) if row.order_id else None,
                    "business_id": str(row.business_id) if row.business_id else None,
                    "amount": _minor_to_major(int(row.amount_minor or amount_minor or 0)),
                    "currency": currency,
                    "meta": (row.meta or {}),
                }
                db.add(
                    Outbox(
                        topic="pawapay_deposit_initiator",
                        dedupe_key=f"deposit:{deposit_id}:initiator",
                        destination=f"{target_base}/events/payment_success",
                        payload=initiator_event,
                    )
                )
            else:
                initiator_event = {
                    "event_id": f"deposit-{deposit_id}",
                    "event_type": "payment_failed",
                    "occurred_at": occurred_at_iso,
                    "correlation_id": correlation_id,
                    "producer": "payment-revenue",
                    "payment_id": deposit_id,
                    "order_id": str(row.order_id) if row.order_id else None,
                    "business_id": str(row.business_id) if row.business_id else None,
                    "amount": _minor_to_major(int(row.amount_minor or amount_minor or 0)),
                    "currency": currency,
                    "failure_code": row.failure_code,
                    "failure_message": row.failure_message,
                    "meta": (row.meta or {}),
                }
                db.add(
                    Outbox(
                        topic="pawapay_deposit_initiator",
                        dedupe_key=f"deposit:{deposit_id}:initiator_failed",
                        destination=f"{target_base}/events/payment_failed",
                        payload=initiator_event,
                    )
                )

        try:
            base_notif = get_notification_base_url().rstrip("/")
        except Exception:
            base_notif = None
        # 2) Notify on failures or missing context (keeps callbacks visible).
        # Also notify if internal processing is disabled (missing INTERNAL_SERVICE_SECRET).
        if base_notif and (status != "COMPLETED" or not (row.order_id and row.business_id) or not internal_secret):
            notif_payload = {
                "channel": "in_app",
                "user_id": None,
                "business_id": row.business_id,
                "template": "pawapay_deposit",
                "payload": payload_event,
            }
            db.add(
                Outbox(
                    topic="notification",
                    dedupe_key=str(payload_event["event_id"]),
                    destination=f"{base_notif}/notification/send",
                    payload=notif_payload,
                )
            )

    try:
        await db.commit()
    except IntegrityError:
        # Most commonly duplicate outbox dedupe_key due to callback retries.
        await db.rollback()

    return {"ok": True}


@app.post("/callbacks/pawapay/payouts")
async def pawapay_payout_callback(request: Request, db: AsyncSession = Depends(get_db_session)):
    _require_pawapay_callback_secret(request)
    raw = await request.body()
    if not raw or raw.strip() == b"":
        logger.error("empty_pawapay_callback_body", extra={"path": request.url.path})
        return JSONResponse(status_code=400, content={"detail": "empty_body"})
    try:
        body = json.loads(raw)
    except Exception:
        logger.error("malformed_pawapay_callback_json", extra={"path": request.url.path, "raw": raw.decode("utf-8", errors="replace")})
        return JSONResponse(status_code=400, content={"detail": "malformed_json"})
    payout_id = str(body.get("payoutId") or "").strip()
    if not payout_id:
        raise HTTPException(status_code=400, detail="missing_payoutId")

    recipient = body.get("recipient") if isinstance(body.get("recipient"), dict) else {}
    acct = recipient.get("accountDetails") if isinstance(recipient.get("accountDetails"), dict) else {}
    phone = acct.get("phoneNumber")
    provider = acct.get("provider")

    status = str(body.get("status") or "UNKNOWN")
    amount_minor = _pawapay_amount_to_minor(body.get("amount"))
    currency = str(body.get("currency") or "ZMW").upper()
    failure_code, failure_message = _extract_failure(body)

    row = (await db.execute(select(PawaPayPayout).where(PawaPayPayout.payout_id == payout_id))).scalar_one_or_none()
    if not row:
        row = PawaPayPayout(
            payout_id=payout_id,
            currency=currency,
            amount_minor=amount_minor,
            phone_number=str(phone) if phone else None,
            provider=str(provider) if provider else None,
            status=status,
            failure_code=failure_code,
            failure_message=failure_message,
            meta={"callback": body},
        )
        db.add(row)
    else:
        row.status = status
        if amount_minor:
            row.amount_minor = int(amount_minor)
        row.currency = currency
        row.phone_number = str(phone) if phone else row.phone_number
        row.provider = str(provider) if provider else row.provider
        row.failure_code = failure_code
        row.failure_message = failure_message
        row.meta = {**(row.meta or {}), "callback": body}
        row.updated_at = _utcnow()

    # Always persist the callback update quickly, even if outbox insert is a duplicate.
    await db.commit()

    # Persist outbox events for terminal statuses so downstream services can be notified asynchronously.
    if status in _PAWAPAY_TERMINAL:
        correlation_id = getattr(request.state, "correlation_id", None) or request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        payload_event = {
                "event_id": f"payout-{payout_id}",
                "event_type": "pawapay_payout",
                "occurred_at": _utcnow().isoformat().replace("+00:00", "Z"),
                "correlation_id": correlation_id,
                "producer": "payment-revenue",
                "payout_id": payout_id,
                "status": status,
                "amount": _minor_to_major(int(amount_minor or 0)),
                "currency": currency,
                "phone_number": row.phone_number,
                "provider": row.provider,
                "meta": row.meta or {},
        }

        try:
            base_notif = get_notification_base_url().rstrip("/")
        except Exception:
            base_notif = None
        if base_notif:
            notif_payload = {
                "channel": "in_app",
                "user_id": None,
                "business_id": row.business_id,
                "template": "pawapay_payout",
                "payload": payload_event,
            }
            db.add(
                Outbox(
                    topic="notification",
                    dedupe_key=str(payload_event["event_id"]),
                    destination=f"{base_notif}/notification/send",
                    payload=notif_payload,
                )
            )

    try:
        await db.commit()
    except IntegrityError:
        # Most commonly duplicate outbox dedupe_key due to callback retries.
        await db.rollback()

    return {"ok": True}


@app.post("/callbacks/pawapay/refunds")
async def pawapay_refund_callback(request: Request, db: AsyncSession = Depends(get_db_session)):
    _require_pawapay_callback_secret(request)
    raw = await request.body()
    if not raw or raw.strip() == b"":
        logger.error("empty_pawapay_callback_body", extra={"path": request.url.path})
        return JSONResponse(status_code=400, content={"detail": "empty_body"})
    try:
        body = json.loads(raw)
    except Exception:
        logger.error("malformed_pawapay_callback_json", extra={"path": request.url.path, "raw": raw.decode("utf-8", errors="replace")})
        return JSONResponse(status_code=400, content={"detail": "malformed_json"})
    refund_id = str(body.get("refundId") or body.get("payoutId") or "").strip()
    if not refund_id:
        raise HTTPException(status_code=400, detail="missing_refundId")

    status = str(body.get("status") or "UNKNOWN")
    amount_minor = _pawapay_amount_to_minor(body.get("amount"))
    currency = str(body.get("currency") or "ZMW").upper()
    failure_code, failure_message = _extract_failure(body)

    row = (await db.execute(select(PawaPayRefund).where(PawaPayRefund.refund_id == refund_id))).scalar_one_or_none()
    if not row:
        row = PawaPayRefund(
            refund_id=refund_id,
            deposit_id=str(body.get("depositId")) if body.get("depositId") else None,
            currency=currency,
            amount_minor=amount_minor,
            status=status,
            failure_code=failure_code,
            failure_message=failure_message,
            meta={"callback": body},
        )
        db.add(row)
    else:
        row.status = status
        if amount_minor:
            row.amount_minor = int(amount_minor)
        row.currency = currency
        row.deposit_id = str(body.get("depositId")) if body.get("depositId") else row.deposit_id
        row.failure_code = failure_code
        row.failure_message = failure_message
        row.meta = {**(row.meta or {}), "callback": body}
        row.updated_at = _utcnow()

    # Always persist the callback update quickly, even if outbox insert is a duplicate.
    await db.commit()

    # Persist outbox events for terminal statuses so downstream services can be notified asynchronously.
    if status in _PAWAPAY_TERMINAL:
        correlation_id = getattr(request.state, "correlation_id", None) or request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        payload_event = {
                "event_id": f"refund-{refund_id}",
                "event_type": "pawapay_refund",
                "occurred_at": _utcnow().isoformat().replace("+00:00", "Z"),
                "correlation_id": correlation_id,
                "producer": "payment-revenue",
                "refund_id": refund_id,
                "deposit_id": row.deposit_id if row else (str(body.get("depositId")) if body.get("depositId") else None),
                "status": status,
                "amount": _minor_to_major(int(amount_minor or 0)),
                "currency": currency,
                "meta": row.meta if row else (body or {}),
        }

        try:
            base_notif = get_notification_base_url().rstrip("/")
        except Exception:
            base_notif = None
        if base_notif:
            notif_payload = {
                "channel": "in_app",
                "user_id": None,
                "business_id": row.business_id if row else None,
                "template": "pawapay_refund",
                "payload": payload_event,
            }
            db.add(
                Outbox(
                    topic="notification",
                    dedupe_key=str(payload_event["event_id"]),
                    destination=f"{base_notif}/notification/send",
                    payload=notif_payload,
                )
            )

    try:
        await db.commit()
    except IntegrityError:
        # Most commonly duplicate outbox dedupe_key due to callback retries.
        await db.rollback()

    return {"ok": True}


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

                affiliate_event = _build_affiliate_event(
                    event_id=f"settle-{existing.id}",
                    correlation_id=correlation_id,
                    payment_id=existing.payment_id,
                    order_id=existing.order_id,
                    business_id=existing.business_id,
                    user_phone=payload.user_phone,
                    amount_minor=int(existing.amount_minor),
                    currency=existing.currency,
                    msme_amount_minor=int(existing.msme_net_minor),
                    affiliate_amount_minor=int(existing.affiliate_commission_minor),
                    platform_amount_minor=int(existing.platform_fee_minor) - int(existing.affiliate_commission_minor),
                    affiliate_id=None,
                    affiliate_code=(existing.meta.get("affiliate_code") if isinstance(existing.meta, dict) else None),
                    occurred_at=occurred_at_iso,
                )

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

        affiliate_event = _build_affiliate_event(
            event_id=f"settle-{s.id}",
            correlation_id=correlation_id,
            payment_id=payload.payment_id,
            order_id=payload.order_id,
            business_id=payload.business_id,
            user_phone=payload.user_phone,
            amount_minor=int(payload.amount_minor),
            currency=payload.currency,
            msme_amount_minor=int(msme_net),
            affiliate_amount_minor=int(affiliate_commission),
            platform_amount_minor=int(platform_net),
            affiliate_id=None,
            affiliate_code=(payload.metadata or {}).get("affiliate_code"),
            occurred_at=occurred_at,
        )

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
