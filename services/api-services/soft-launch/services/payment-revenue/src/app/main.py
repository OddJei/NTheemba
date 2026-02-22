from __future__ import annotations

import logging
import asyncio
import time
import uuid
import re
import secrets
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import httpx
import json
import hmac
import hashlib
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import select, text, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.config import (
    get_admin_key,
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
from src.app.models import Outbox, PawaPayDeposit, PawaPayPayout, PawaPayRefund, Payout, Settlement, SubscriptionPayment, MSMEPayout, MSMEPayoutRecord, AffiliatePayoutRecord, PlatformFee
from src.app.helpers.outbox.outbox import create_outbox_row
from src.app.schemas import (
    AffiliatePayoutOut,
    GrossRevenueOut,
    MSMEPayoutInitiateIn,
    MSMEPayoutOut,
    PaymentSuccessIn,
    PayoutBatchRequestIn,
    PayoutBatchResponseOut,
    PawaPayDepositInitiateIn,
    PawaPayPayoutInitiateIn,
    PawaPayRefundInitiateIn,
    PawaPayTxnOut,
    PlatformBalanceOut,
    PayoutOut,
    RefundOut,
    RefundRequestIn,
    OutboxAckRequest,
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
    # Internal service endpoints (order-delivery calls to initiate payment)
    "/pawapay/deposits/initiate",
    "/pawapay/payouts/initiate",
    # Admin endpoints (use X-Admin-Key instead of Bearer token)
    "/admin/gross-revenue",
    "/admin/platform-balance",
    "/epoch",
    "/payout/batch",
    # MSME payout endpoints
    "/msme/payouts/initiate",
    "/msme/payouts",
    "/events/msme-payout-initiate",
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

    sql = text(
        """
        SELECT id, topic, payload::text as payload, destination, dedupe_key, attempts, send_after, correlation_id
        FROM public.outbox
        WHERE status = 'pending' AND (send_after IS NULL OR send_after <= :now)
        ORDER BY created_at ASC
        LIMIT :limit
        """
    )
    res = await db.execute(sql, {"now": now, "limit": int(batch_size)})
    rows = res.fetchall()

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
                # row may be a DB row tuple when selected from public.outbox
                dest = getattr(row, "destination", None) or row.destination
                payload_text = getattr(row, "payload", None) or row.payload
                try:
                    payload = json.loads(payload_text) if payload_text else {}
                except Exception:
                    payload = {}
                r = await client.post(dest, json=payload, headers=headers)
                if 200 <= r.status_code < 300:
                    await db.execute(text("UPDATE public.outbox SET status='sent', last_error=NULL, attempts = COALESCE(attempts,0) + 1, updated_at = :now WHERE id = :id"), {"id": row.id, "now": _utcnow()})
                    await db.commit()
                    results["sent"] += 1
                else:
                    if _should_mark_failed_http(r.status_code) or (max_attempts > 0 and (int(getattr(row, "attempts", 0) or 0) + 1) >= max_attempts):
                        await db.execute(text("UPDATE public.outbox SET status='failed', last_error = :err, attempts = COALESCE(attempts,0) + 1, updated_at = :now WHERE id = :id"), {"id": row.id, "err": f"http_{r.status_code}", "now": _utcnow()})
                        await db.commit()
                        results["failed"] += 1
                    else:
                        # schedule retry by setting send_after
                        backoff_base = get_outbox_flush_backoff_base_seconds()
                        attempts = int(getattr(row, "attempts", 0) or 0) + 1
                        backoff = min(backoff_base * (2 ** max(0, attempts - 1)), get_outbox_flush_backoff_max_seconds())
                        next_send = datetime.now(timezone.utc) + timedelta(seconds=backoff)
                        await db.execute(text("UPDATE public.outbox SET send_after = :send_after, attempts = COALESCE(attempts,0) + 1, last_error = :err, updated_at = :now WHERE id = :id"), {"id": row.id, "send_after": next_send, "err": f"http_{r.status_code}", "now": _utcnow()})
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


@app.post("/events/order-delivered")
async def order_delivered_event(
    request: Request,
    payload: dict,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    """Handle delivery-confirmed event from order-delivery.

    This endpoint idempotently persists a `PlatformFee` row when delivery is
    confirmed, but only if no completed refund exists for the same deposit_id
    or order_id. Expects payload to contain `order_id` and optionally
    `deposit_id` and `platform_fee_minor`.
    """
    correlation_id = request.headers.get("X-Correlation-Id") or getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    key = x_idempotency_key or str(payload.get("event_id") or f"order-delivered-{payload.get('order_id')}")

    async def _run():
        order_id = payload.get("order_id")
        deposit_id = payload.get("deposit_id")
        if not order_id and not deposit_id:
            raise HTTPException(status_code=400, detail="missing_order_or_deposit_id")

        # If a completed refund exists for this deposit/order, do not insert
        # a platform fee row.
        refund_q = select(PawaPayRefund).where(PawaPayRefund.status == "COMPLETED")
        if deposit_id:
            refund_q = refund_q.where(PawaPayRefund.deposit_id == deposit_id)
        else:
            refund_q = refund_q.where(PawaPayRefund.order_id == order_id)
        refund_row = (await db.execute(refund_q)).scalar_one_or_none()
        if refund_row:
            return 200, {"ok": False, "reason": "already_refunded"}

        # Check for existing platform fee for this deposit/order
        pf_q = select(PlatformFee)
        conds = []
        if deposit_id:
            conds.append(PlatformFee.deposit_id == deposit_id)
        if order_id:
            conds.append(PlatformFee.order_id == order_id)
        if conds:
            from sqlalchemy import or_

            pf_q = pf_q.where(or_(*conds))
            existing_pf = (await db.execute(pf_q)).scalar_one_or_none()
            if existing_pf:
                return 200, {"ok": True, "id": existing_pf.id, "created": False}

        # Determine platform fee amount: prefer explicit in payload, fall back to deposit/settlement
        try:
            pf_amt = int(payload.get("platform_fee_minor") or 0)
        except Exception:
            pf_amt = 0

        s = None
        if pf_amt <= 0:
            # Try deposit
            if deposit_id:
                dep = (await db.execute(select(PawaPayDeposit).where(PawaPayDeposit.deposit_id == deposit_id))).scalar_one_or_none()
                if dep:
                    pf_amt = int(getattr(dep, "platform_fee_minor", 0) or 0)
        if pf_amt <= 0 and order_id:
            s = (await db.execute(select(Settlement).where(Settlement.order_id == order_id))).scalar_one_or_none()
            if s:
                pf_amt = int(getattr(s, "platform_fee_minor", 0) or 0)

        if pf_amt <= 0:
            return 200, {"ok": False, "reason": "no_platform_fee"}

        # Attempt an atomic insert that ensures:
        # - no completed refund exists for this deposit/order
        # - no platform_fees row already exists for this deposit/order
        schema = get_pg_schema() or "public"
        meta_json = json.dumps({"source": "order_delivered_event", "payload": payload})
        sql = f'''
        WITH ins AS (
          INSERT INTO "{schema}".platform_fees (id, deposit_id, order_id, currency, amount_minor, meta, created_at, updated_at)
          SELECT :id, :deposit_id, :order_id, :currency, :amount_minor, :meta::jsonb, now(), now()
          WHERE NOT EXISTS (
            SELECT 1 FROM "{schema}".pawapay_refunds r
            WHERE r.status = 'COMPLETED' AND ((:deposit_id IS NOT NULL AND r.deposit_id = :deposit_id) OR (:order_id IS NOT NULL AND r.order_id = :order_id))
          )
          AND NOT EXISTS (
            SELECT 1 FROM "{schema}".platform_fees p
            WHERE (:deposit_id IS NOT NULL AND p.deposit_id = :deposit_id) OR (:order_id IS NOT NULL AND p.order_id = :order_id)
          )
          RETURNING id
        )
        SELECT id FROM ins;
        '''

        params = {
            "id": str(uuid.uuid4()),
            "deposit_id": deposit_id,
            "order_id": order_id,
            "currency": str(payload.get("currency") or (getattr(s, "currency", None) if s is not None else "ZMW")),
            "amount_minor": int(pf_amt),
            "meta": meta_json,
        }

        try:
            res = await db.execute(text(sql), params)
            row = res.first()
        except IntegrityError as ie:
            await db.rollback()
            logger.warning("platform_fee_insert_integrity_error", extra={"order_id": order_id, "deposit_id": deposit_id, "error": str(ie), "correlation_id": correlation_id})
            row = None

        if row and row[0]:
            logger.info("platform_fee_inserted", extra={"order_id": order_id, "deposit_id": deposit_id, "id": str(row[0]), "amount_minor": pf_amt, "correlation_id": correlation_id})
            return 201, {"ok": True, "id": str(row[0]), "created": True}

        # If no row returned, someone else inserted concurrently or insert blocked by refund check
        existing_pf = (await db.execute(pf_q)).scalar_one_or_none()
        if existing_pf:
            logger.info("platform_fee_already_exists", extra={"order_id": order_id, "deposit_id": deposit_id, "id": existing_pf.id, "correlation_id": correlation_id})
            return 200, {"ok": True, "id": existing_pf.id, "created": False}

        logger.info("platform_fee_not_inserted", extra={"order_id": order_id, "deposit_id": deposit_id, "reason": "not_inserted_or_refunded", "correlation_id": correlation_id})
        return 200, {"ok": False, "reason": "not_inserted"}

    status, body = await idempotent_execute(db=db, scope=scope_for("POST", request.url.path), key=key, run=_run)
    response.status_code = int(status)
    return body
def _txn_out(*, external_id: str, status: str, amount_minor: int, currency: str, provider: str | None, phone_number: str | None, platform_fee_minor: int | None = 0, fee_bps: int | None = None, payment_type: str | None = None, msme_net_minor: int | None = 0, provider_transaction_id: str | None = None, meta: dict | None) -> PawaPayTxnOut:
    return PawaPayTxnOut(
        external_id=str(external_id),
        status=str(status),
        amount_minor=int(amount_minor or 0),
        currency=str(currency or "ZMW"),
        provider=provider,
        phone_number=phone_number,
        platform_fee_minor=int(platform_fee_minor or 0),
        fee_bps=int(fee_bps) if fee_bps is not None else None,
        payment_type=payment_type,
        msme_net_minor=int(msme_net_minor or 0),
        provider_transaction_id=provider_transaction_id,
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


def _require_admin_key(x_admin_key: str | None) -> None:
    expected = str(get_admin_key() or "").strip()
    provided = str(x_admin_key or "").strip()
    if expected and provided != expected:
        raise HTTPException(status_code=401, detail="invalid_admin_key")


def _parse_iso_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    v = str(value).strip()
    if v.endswith("Z"):
        v = v.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


async def _fetch_epoch_window(epoch_id: str) -> tuple[datetime, datetime]:
    base = get_affiliate_engine_base_url().rstrip("/")
    timeout = get_http_timeout_seconds()
    headers = {"X-Admin-Key": get_admin_key()}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(f"{base}/admin/epochs", headers=headers)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="affiliate_engine_epoch_lookup_failed")
    data = r.json() if isinstance(r.json(), list) else []
    for e in data:
        if str(e.get("id")) == str(epoch_id):
            starts_at = _parse_iso_dt(e.get("starts_at"))
            ends_at = _parse_iso_dt(e.get("ends_at")) or _utcnow()
            if not starts_at:
                break
            return starts_at, ends_at
    raise HTTPException(status_code=404, detail="epoch_not_found")


async def _get_msme_subscription_status(
    business_id: str,
    authorization: str,
    correlation_id: str,
) -> str:
    """
    Fetch MSME subscription status from msme-engine.
    Returns 'ACTIVE' if subscription is active, otherwise 'INACTIVE'.
    """
    msme_base = os.getenv("MSME_ENGINE_URL", "http://msme-engine:8520")
    url = f"{msme_base}/business/{business_id}/subscription"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                url,
                headers={
                    "Authorization": authorization,
                    "X-Correlation-Id": correlation_id,
                },
            )
            if resp.status_code == 404:
                # No subscription found, treat as inactive
                logger.info(f"msme_subscription_not_found business_id={business_id}")
                return "INACTIVE"
            elif resp.status_code != 200:
                logger.warning(f"msme_engine_subscription_fetch_failed business_id={business_id} status={resp.status_code}")
                return "INACTIVE"
            
            data = resp.json()
            status = data.get("status", "INACTIVE")
            logger.info(f"msme_subscription_fetched business_id={business_id} status={status}")
            return status
        except Exception as e:
            logger.exception(f"error_fetching_subscription business_id={business_id}")
            return "INACTIVE"


async def _filter_delivered_orders(order_ids: list[str], authorization: str | None, correlation_id: str | None) -> set[str]:
    if not order_ids:
        return set()
    sem = asyncio.Semaphore(10)

    async def _check(order_id: str) -> str | None:
        async with sem:
            try:
                ok = await delivery_is_confirmed(order_id=order_id, authorization=authorization, correlation_id=correlation_id)
                return order_id if ok else None
            except Exception:
                return None

    results = await asyncio.gather(*[_check(oid) for oid in order_ids])
    return {r for r in results if r}


async def _platform_fee_revenue_minor(
    db: AsyncSession,
    start_date: datetime | None,
    end_date: datetime | None,
    *,
    require_delivery: bool = True,
) -> tuple[int, int]:
    # New behaviour: derive platform fee revenue from `platform_fees` table
    # and subtract refunds only when refund rows reference deposits/orders
    # that exist in `platform_fees`.
    pf_q = select(func.coalesce(func.sum(PlatformFee.amount_minor), 0), func.count(PlatformFee.id))
    if start_date:
        pf_q = pf_q.where(PlatformFee.created_at >= start_date)
    if end_date:
        pf_q = pf_q.where(PlatformFee.created_at <= end_date)

    pf_sum_minor, pf_count = (await db.execute(pf_q)).first() or (0, 0)

    # Sum refunded platform fees that reference records in platform_fees
    schema = get_pg_schema() or "public"
    refunded_sql = f'''
    SELECT COALESCE(SUM(r.platform_fee_minor), 0) FROM "{schema}".pawapay_refunds r
    JOIN "{schema}".platform_fees p
      ON (r.deposit_id IS NOT NULL AND r.deposit_id = p.deposit_id)
         OR (r.order_id IS NOT NULL AND r.order_id = p.order_id)
    WHERE r.status = 'COMPLETED'
    '''
    params: dict = {}
    if start_date:
        refunded_sql += " AND r.updated_at >= :start"
        params["start"] = start_date
    if end_date:
        refunded_sql += " AND r.updated_at <= :end"
        params["end"] = end_date

    res = await db.execute(text(refunded_sql), params)
    refunded_pf_minor = int((res.first() or (0,))[0] or 0)

    total = int(pf_sum_minor or 0) - int(refunded_pf_minor or 0)
    return total, int(pf_count or 0)


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


@app.post("/msme/payouts/initiate", response_model=MSMEPayoutOut)
async def initiate_msme_payout(
    payload: MSMEPayoutInitiateIn,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Initiate MSME payout for a delivered order.
    
    FLOW:
    1. Verify order exists and payment was successful
    2. Calculate platform fee and MSME payout
    3. Initiate PawaPay payout to MSME
    4. Record MSME payout status
    5. Record in gross revenue
    """
    correlation_id = str(uuid.uuid4())
    
    # 1. Check if settlement exists
    settlement = (
        await db.execute(select(Settlement).where(Settlement.order_id == payload.order_id))
    ).scalar_one_or_none()
    if not settlement:
        raise HTTPException(status_code=404, detail="settlement_not_found")
    
    # 2. Check if MSME payout already initiated
    existing = (
        await db.execute(select(MSMEPayoutRecord).where(MSMEPayoutRecord.order_id == payload.order_id))
    ).scalar_one_or_none()
    if existing:
        # Get msme_phone from stored request
        request_data = existing.meta.get("request", {})
        msme_phone = request_data.get("msme_phone")
        provider = _infer_provider_from_phone(msme_phone) if msme_phone else None
        return MSMEPayoutOut(
            id=existing.id,
            payout_id=existing.payout_id,
            order_id=existing.order_id,
            business_id=existing.business_id,
            msme_phone=msme_phone,
            provider=provider,
            amount_minor=int(existing.msme_payout_minor),
            platform_fee_minor=int(existing.platform_fee_minor),
            currency=existing.currency,
            status=existing.status,
            failure_code=None,
            failure_message=existing.error_message,
            initiated_at=existing.initiated_at,
            completed_at=existing.completed_at,
        )
    
    # 3. Calculate fees
    # Prefer platform fee recorded on the settlement (persisted from deposit),
    # fall back to explicit `platform_fee_minor` passed in metadata, else 0.
    try:
        order_amount_minor_val = int(payload.order_amount_minor)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_order_amount_minor")

    # settlement.platform_fee_minor may be None/0
    try:
        platform_fee_minor = int(settlement.platform_fee_minor or 0)
    except Exception:
        platform_fee_minor = 0

    if not platform_fee_minor:
        # metadata may include platform_fee_minor
        platform_fee_minor = int((payload.metadata or {}).get("platform_fee_minor") or 0)

    msme_payout_minor = max(0, order_amount_minor_val - int(platform_fee_minor))
    
    # 4. Create record
    record = MSMEPayoutRecord(
        order_id=payload.order_id,
        business_id=payload.business_id,
        currency=payload.currency,
        order_amount_minor=int(payload.order_amount_minor),
        platform_fee_minor=int(platform_fee_minor),
        msme_payout_minor=int(msme_payout_minor),
        status="pending",
        meta={
            "request": payload.model_dump(mode="json"),
            "correlation_id": correlation_id,
            **(payload.metadata or {}),
        },
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    
    # 5. Infer msme phone and provider
    msme_phone = payload.msme_phone
    provider = _infer_provider_from_phone(msme_phone) or "UNKNOWN"
    
    # 6. Return immediately (payout will be initiated async in background)
    response.status_code = 202
    from datetime import datetime, timezone
    initiated_at = record.initiated_at or datetime.now(timezone.utc)
    return {
        "id": record.id,
        "payout_id": record.payout_id,
        "order_id": record.order_id,
        "business_id": record.business_id,
        "msme_phone": msme_phone,
        "provider": provider,
        "amount_minor": int(record.msme_payout_minor),
        "platform_fee_minor": int(record.platform_fee_minor),
        "currency": record.currency,
        "status": record.status,
        "failure_code": None,
        "failure_message": record.error_message,
        "initiated_at": initiated_at,
        "completed_at": record.completed_at,
    }


@app.get("/msme/payouts/{order_id}", response_model=MSMEPayoutOut)
async def get_msme_payout(order_id: str, db: AsyncSession = Depends(get_db_session)):
    """Get MSME payout status for an order."""
    record = (
        await db.execute(select(MSMEPayoutRecord).where(MSMEPayoutRecord.order_id == order_id))
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="msme_payout_not_found")
    
    # Get msme_phone from stored request
    request_data = record.meta.get("request", {})
    msme_phone = request_data.get("msme_phone")
    provider = _infer_provider_from_phone(msme_phone) if msme_phone else None
    
    return MSMEPayoutOut(
        id=record.id,
        payout_id=record.payout_id,
        order_id=record.order_id,
        business_id=record.business_id,
        msme_phone=msme_phone,
        provider=provider,
        amount_minor=int(record.msme_payout_minor),
        platform_fee_minor=int(record.platform_fee_minor),
        currency=record.currency,
        status=record.status,
        failure_code=None,
        failure_message=record.error_message,
        initiated_at=record.initiated_at,
        completed_at=record.completed_at,
    )



@app.get("/admin/gross-revenue", response_model=GrossRevenueOut)
async def get_gross_revenue(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db_session),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    _require_admin_key(x_admin_key)

    sub_q = select(
        func.coalesce(func.sum(SubscriptionPayment.amount_minor), 0),
        func.count(SubscriptionPayment.id),
    ).where(SubscriptionPayment.status == "dispatched")
    if start_date:
        sub_q = sub_q.where(SubscriptionPayment.created_at >= start_date)
    if end_date:
        sub_q = sub_q.where(SubscriptionPayment.created_at <= end_date)

    sub_sum_minor, sub_count = (await db.execute(sub_q)).first() or (0, 0)

    platform_fee_minor, platform_count = await _platform_fee_revenue_minor(
        db,
        start_date,
        end_date,
        require_delivery=True,
    )

    gross_minor = int(sub_sum_minor or 0) + int(platform_fee_minor or 0)

    return GrossRevenueOut(
        gross_revenue_zmw=_minor_to_major(int(gross_minor)),
        subscription_revenue_zmw=_minor_to_major(int(sub_sum_minor or 0)),
        platform_fee_revenue_zmw=_minor_to_major(int(platform_fee_minor or 0)),
        transaction_count=int(sub_count or 0) + int(platform_count or 0),
        start_date=start_date,
        end_date=end_date,
        calculated_at=_utcnow(),
    )


@app.get("/epoch/{epoch_id}/gross-revenue", response_model=GrossRevenueOut)
async def get_epoch_gross_revenue(
    epoch_id: str,
    db: AsyncSession = Depends(get_db_session),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    _require_admin_key(x_admin_key)

    start_date, end_date = await _fetch_epoch_window(epoch_id)

    sub_q = select(
        func.coalesce(func.sum(SubscriptionPayment.amount_minor), 0),
        func.count(SubscriptionPayment.id),
    ).where(
        SubscriptionPayment.status == "dispatched",
        SubscriptionPayment.created_at >= start_date,
        SubscriptionPayment.created_at <= end_date,
    )
    sub_sum_minor, sub_count = (await db.execute(sub_q)).first() or (0, 0)

    platform_fee_minor, platform_count = await _platform_fee_revenue_minor(
        db,
        start_date,
        end_date,
        require_delivery=True,
    )

    gross_minor = int(sub_sum_minor or 0) + int(platform_fee_minor or 0)

    return GrossRevenueOut(
        gross_revenue_zmw=_minor_to_major(int(gross_minor)),
        subscription_revenue_zmw=_minor_to_major(int(sub_sum_minor or 0)),
        platform_fee_revenue_zmw=_minor_to_major(int(platform_fee_minor or 0)),
        transaction_count=int(sub_count or 0) + int(platform_count or 0),
        start_date=start_date,
        end_date=end_date,
        epoch_id=epoch_id,
        calculated_at=_utcnow(),
    )


@app.get("/internal/gross-revenue", response_model=GrossRevenueOut)
async def get_internal_gross_revenue(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Internal endpoint for other services to query gross revenue for a period.

    This endpoint intentionally skips the `X-Admin-Key` check and is meant to be
    called from trusted internal services only (deploy network control / firewall
    rules should restrict access).
    """

    sub_q = select(
        func.coalesce(func.sum(SubscriptionPayment.amount_minor), 0),
        func.count(SubscriptionPayment.id),
    ).where(SubscriptionPayment.status == "dispatched")
    if start_date:
        sub_q = sub_q.where(SubscriptionPayment.created_at >= start_date)
    if end_date:
        sub_q = sub_q.where(SubscriptionPayment.created_at <= end_date)

    sub_sum_minor, sub_count = (await db.execute(sub_q)).first() or (0, 0)

    platform_fee_minor, platform_count = await _platform_fee_revenue_minor(
        db,
        start_date,
        end_date,
        require_delivery=True,
    )

    gross_minor = int(sub_sum_minor or 0) + int(platform_fee_minor or 0)

    return GrossRevenueOut(
        gross_revenue_zmw=_minor_to_major(int(gross_minor)),
        subscription_revenue_zmw=_minor_to_major(int(sub_sum_minor or 0)),
        platform_fee_revenue_zmw=_minor_to_major(int(platform_fee_minor or 0)),
        transaction_count=int(sub_count or 0) + int(platform_count or 0),
        start_date=start_date,
        end_date=end_date,
        calculated_at=_utcnow(),
    )


@app.post("/payout/batch", response_model=PayoutBatchResponseOut, status_code=202)
async def initiate_payout_batch(
    payload: PayoutBatchRequestIn,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """
    Request batch payout to affiliates from affiliate-engine.
    
    Flow:
    1. Validate request
    2. Create payout records for each affiliate
    3. Initiate PawaPay transfers
    4. Return batch status with payout IDs
    5. Send callback to affiliate-engine when payouts complete
    
    Args:
        payload: Batch containing epoch_id, list of payouts, callback_url
    
    Returns:
        202 Accepted with batch_id and individual payout IDs
    """
    _require_admin_key(x_admin_key)
    
    batch_id = str(uuid.uuid4())
    correlation_id = f"batch-{batch_id}"
    
    logger.info(f"payout_batch_initiated batch_id={batch_id} epoch_id={payload.epoch_id} count={len(payload.payouts)}")
    
    payout_records = []
    payout_responses = []
    total_amount = 0.0
    
    # Pre-populate response data and create records
    for payout_req in payload.payouts:
        payout_id = str(uuid.uuid4())
        
        # Build response immediately for 202 return
        payout_responses.append(
            AffiliatePayoutOut(
                affiliate_id=payout_req.affiliate_id,
                payout_id=payout_id,
                amount_zmw=payout_req.amount_zmw,
                currency=payout_req.currency,
                status="ACCEPTED",
                initiated_at=_utcnow(),
            )
        )
        total_amount += payout_req.amount_zmw
    
    async def _process_payouts():
        """Process all payouts and send callback when done."""
        try:
            # In production, integrate with PawaPay here
            # For now, we simulate immediate processing
            
            await asyncio.sleep(0.1)  # Simulate async processing
            
            # Send callback to affiliate-engine  
            try:
                async with httpx.AsyncClient() as client:
                    for payout_resp in payout_responses:
                        callback_payload = {
                            "payout_id": payout_resp.payout_id,
                            "epoch_id": payload.epoch_id,
                            "affiliate_id": payout_resp.affiliate_id,
                            "status": "completed",
                            "amount_zmw": payout_resp.amount_zmw,
                            "error_message": None,
                            "completed_at": _utcnow().isoformat(),
                        }
                        body_bytes = json.dumps(callback_payload, separators=(",",":"), ensure_ascii=False).encode("utf-8")
                        signature = None
                        try:
                            secret = os.environ.get("PAYMENT_REVENUE_HMAC_SECRET", "").encode("utf-8")
                            if secret:
                                sig = hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()
                                signature = f"sha256={sig}"
                        except Exception:
                            signature = None

                        headers = {
                            "X-Admin-Key": get_admin_key(),
                            "X-Service": "payment-revenue",
                        }
                        if signature:
                            headers["X-Payment-Signature"] = signature

                        response = await client.post(
                            payload.callback_url,
                            content=body_bytes,
                            headers=headers,
                            timeout=10.0,
                        )
                        
                        logger.info(
                            f"payout_callback sent payout_id={payout_resp.payout_id} "
                            f"status_code={response.status_code}"
                        )
                        
                        if response.status_code != 200:
                            logger.warning(
                                f"callback_failed payout_id={payout_resp.payout_id} "
                                f"status_code={response.status_code}"
                            )
            except Exception as e:
                logger.exception(f"callback_error batch_id={batch_id} error={e}")
        except Exception as e:
            logger.exception(f"payout_processing_error batch_id={batch_id} error={e}")
    
    # Start background task
    asyncio.create_task(_process_payouts())
    
    return PayoutBatchResponseOut(
        batch_id=batch_id,
        epoch_id=payload.epoch_id,
        total_payouts=len(payload.payouts),
        total_amount_zmw=total_amount,
        payouts=payout_responses,
        status="ACCEPTED",
        initiated_at=_utcnow(),
    )


@app.get("/admin/platform-balance", response_model=PlatformBalanceOut)
async def get_platform_balance(
    db: AsyncSession = Depends(get_db_session),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    _require_admin_key(x_admin_key)

    deposits_q = select(func.coalesce(func.sum(PawaPayDeposit.amount_minor), 0)).where(
        PawaPayDeposit.status == "COMPLETED"
    )
    refunds_q = select(func.coalesce(func.sum(PawaPayRefund.amount_minor), 0)).where(
        PawaPayRefund.status == "COMPLETED"
    )
    payouts_q = select(func.coalesce(func.sum(PawaPayPayout.amount_minor), 0)).where(
        PawaPayPayout.status == "COMPLETED"
    )
    subs_q = select(func.coalesce(func.sum(SubscriptionPayment.amount_minor), 0)).where(
        SubscriptionPayment.status == "dispatched"
    )

    deposits_minor = (await db.execute(deposits_q)).scalar() or 0
    refunds_minor = (await db.execute(refunds_q)).scalar() or 0
    payouts_minor = (await db.execute(payouts_q)).scalar() or 0
    subs_minor = (await db.execute(subs_q)).scalar() or 0

    total_inflows_minor = int(deposits_minor or 0) + int(subs_minor or 0)
    total_outflows_minor = int(payouts_minor or 0) + int(refunds_minor or 0)
    balance_minor = total_inflows_minor - total_outflows_minor

    return PlatformBalanceOut(
        platform_balance_zmw=_minor_to_major(int(balance_minor)),
        total_inflows_zmw=_minor_to_major(int(total_inflows_minor)),
        total_outflows_zmw=_minor_to_major(int(total_outflows_minor)),
        calculated_at=_utcnow(),
    )


@app.post("/events/msme-payout-initiate", response_model=MSMEPayoutOut)
async def msme_payout_initiate(
    request: Request,
    payload: MSMEPayoutInitiateIn,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    """
    Initiate MSME payout on order delivery.
    
    FLOW:
    1. Validate MSME subscription is active
    2. Normalize and infer provider from phone
    3. Initiate PawaPay payout
    4. Track payout in MSMEPayout table
    5. Emit audit event
    """
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    key = x_idempotency_key or f"{payload.order_id}-msme"

    _require_zmw(payload.currency)
    normalized_phone, provider = _validate_and_infer_zmb_phone_and_provider(payload.msme_phone, None)

    # Get authorization header for calling msme-engine
    authorization = request.headers.get("Authorization", "")

    async def _run():
        existing = (await db.execute(
            select(MSMEPayout).where(MSMEPayout.order_id == payload.order_id)
        )).scalar_one_or_none()
        if existing:
            return 200, {
                "id": existing.id,
                "payout_id": existing.payout_id,
                "order_id": existing.order_id,
                "business_id": existing.business_id,
                "msme_phone": existing.msme_phone,
                "provider": existing.provider,
                "amount_minor": int(existing.amount_minor),
                "platform_fee_minor": int(existing.platform_fee_minor),
                "currency": existing.currency,
                "status": existing.status,
                "failure_code": existing.failure_code,
                "failure_message": existing.failure_message,
                "initiated_at": existing.initiated_at.isoformat(),
                "completed_at": existing.completed_at.isoformat() if existing.completed_at else None,
            }

        # Fetch subscription status and determine platform fee
        subscription_status = await _get_msme_subscription_status(
            payload.business_id,
            authorization,
            correlation_id,
        )
        
        # Active subscription: 5%, Inactive: 7%
        platform_fee_pct = 0.05 if subscription_status == "ACTIVE" else 0.07
        
        logger.info(
            f"msme_payout_fee_calculation business_id={payload.business_id} "
            f"subscription_status={subscription_status} platform_fee_pct={platform_fee_pct}"
        )
        
        # Calculate platform fee from percentage
        platform_fee_minor = _fee_amount_minor_units(int(payload.order_amount_minor), int(platform_fee_pct * 10000))
        msme_amount_minor = int(payload.order_amount_minor) - platform_fee_minor

        payout_id = str(uuid.uuid4())
        payout = MSMEPayout(
            payout_id=payout_id,
            order_id=payload.order_id,
            business_id=payload.business_id,
            msme_phone=normalized_phone,
            provider=provider,
            currency=payload.currency,
            amount_minor=int(msme_amount_minor),
            platform_fee_minor=int(platform_fee_minor),
            status="PENDING",
            meta={"correlation_id": correlation_id, **(payload.metadata or {})},
        )
        db.add(payout)
        await db.commit()
        await db.refresh(payout)

        try:
            pr = await pawapay_client.initiate_payout(
                payout_id=payout_id,
                amount=_minor_to_pawapay_amount(int(msme_amount_minor)),
                currency=payload.currency,
                phone_number=normalized_phone,
                provider=provider,
                correlation_id=correlation_id,
            )
        except ValueError:
            raise HTTPException(status_code=500, detail="pawapay_config_missing")
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="pawapay_unreachable")

        payout.status = str(pr.body.get("status") or f"HTTP_{pr.status_code}")
        payout.meta = {**(payout.meta or {}), "pawapay_response": pr.body, "pawapay_status_code": pr.status_code}
        await db.commit()
        await db.refresh(payout)

        await audit_client.emit_audit(
            service="payment-revenue",
            event_type="msme_payout_initiated",
            entity_type="msme_payout",
            entity_id=str(payout.id),
            payload={
                "payout_id": payout_id,
                "order_id": payload.order_id,
                "business_id": payload.business_id,
                "amount_zmw": _minor_to_major(int(msme_amount_minor)),
                "platform_fee_zmw": _minor_to_major(int(platform_fee_minor)),
                "msme_phone": normalized_phone,
                "provider": provider,
            },
            metadata={"correlation_id": correlation_id},
        )

        return 201, {
            "id": payout.id,
            "payout_id": payout.payout_id,
            "order_id": payout.order_id,
            "business_id": payout.business_id,
            "msme_phone": payout.msme_phone,
            "provider": payout.provider,
            "amount_minor": int(payout.amount_minor),
            "platform_fee_minor": int(payout.platform_fee_minor),
            "currency": payout.currency,
            "status": payout.status,
            "failure_code": payout.failure_code,
            "failure_message": payout.failure_message,
            "initiated_at": payout.initiated_at.isoformat(),
            "completed_at": payout.completed_at.isoformat() if payout.completed_at else None,
        }

    status, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", request.url.path),
        key=key,
        run=_run,
    )
    response.status_code = int(status)
    return MSMEPayoutOut(**body)


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
        token_initiator_id = token_payload.get("sub") or token_payload.get("service") or token_payload.get("iss")
        token_initiator_role = token_payload.get("role")
        # Prefer explicit initiator declared in payload; fall back to token claims
        initiator_id = getattr(payload, "initiator_id", None) or token_initiator_id
        initiator_role = getattr(payload, "initiator_role", None) or token_initiator_role
        # Extract declared payment_type and msme cut if provided
        payment_type = getattr(payload, "payment_type", None) or (payload.metadata or {}).get("payment_type")
        msme_net_minor = getattr(payload, "msme_net_minor", None) or (payload.metadata or {}).get("msme_net_minor")
        try:
            msme_net_minor_val = int(msme_net_minor) if msme_net_minor is not None else 0
        except Exception:
            msme_net_minor_val = 0

        # Try to derive platform fee if provided in metadata or via amount - msme_net_minor
        platform_fee_minor_val = 0
        fee_bps_val = (payload.metadata or {}).get("fee_bps") or (payload.metadata or {}).get("transaction_fee_bps")
        if (payload.metadata or {}).get("platform_fee_minor") is not None:
            try:
                platform_fee_minor_val = int((payload.metadata or {}).get("platform_fee_minor") or 0)
            except Exception:
                platform_fee_minor_val = 0
        elif msme_net_minor_val and int(payload.amount_minor or 0) > 0:
            platform_fee_minor_val = max(0, int(payload.amount_minor or 0) - int(msme_net_minor_val))

        row = PawaPayDeposit(
            deposit_id=deposit_id,
            order_id=payload.order_id,
            business_id=payload.business_id,
            currency=str(payload.currency).upper(),
            amount_minor=int(payload.amount_minor),
            phone_number=normalized_phone,
            provider=provider,
            status="CREATED",
            platform_fee_minor=int(platform_fee_minor_val),
            fee_bps=int(fee_bps_val) if fee_bps_val is not None else None,
            payment_type=str(payment_type) if payment_type else None,
            msme_net_minor=int(msme_net_minor_val),
            provider_transaction_id=None,
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

        # Route deposit to settlement or subscription table depending on payment_type
        ptype = (row.payment_type or (row.meta or {}).get("payment_type") or "").lower()
        if not ptype:
            # Enforce non-nullable payment_type
            raise HTTPException(status_code=400, detail="missing_payment_type")

        if ptype in ("order", "one_time", "one-time", "one_time", "one-time-order") or ptype.startswith("order"):
            # create a Settlement record (order payments)
            if not row.order_id:
                raise HTTPException(status_code=400, detail="missing_order_id_for_order_payment")

            settlement = Settlement(
                order_id=row.order_id,
                payment_id=row.deposit_id,
                business_id=row.business_id,
                currency=row.currency,
                amount_minor=int(row.amount_minor or 0),
                fee_bps=int(row.fee_bps) if row.fee_bps is not None else 0,
                platform_fee_minor=int(row.platform_fee_minor or 0),
                affiliate_commission_minor=0,
                msme_net_minor=int(row.msme_net_minor or 0),
                status="pending",
                dispatched=False,
                meta={"source": "deposit_initiate", "deposit_id": row.deposit_id, **(row.meta or {})},
            )
            db.add(settlement)
            await db.commit()
            await db.refresh(settlement)

            # NOTE: platform fee persistence was previously done here
            # immediately after creating the Settlement. We now defer
            # insertion of a `PlatformFee` row until delivery confirmation
            # so that only delivered orders are counted as platform revenue.

        elif ptype in ("subscription", "subs", "subscription_payment") or ptype.startswith("sub"):
            # create a SubscriptionPayment record; require plan/paid_until in metadata
            md = row.meta or {}
            plan = md.get("plan") or md.get("subscription_plan") or (payload.metadata or {}).get("plan")
            paid_until_raw = md.get("paid_until") or (payload.metadata or {}).get("paid_until")
            if not plan or not paid_until_raw:
                raise HTTPException(status_code=400, detail="missing_subscription_plan_or_paid_until_in_metadata")

            try:
                from datetime import datetime

                paid_until_dt = datetime.fromisoformat(str(paid_until_raw))
            except Exception:
                raise HTTPException(status_code=400, detail="invalid_paid_until_datetime")

            sub = SubscriptionPayment(
                payment_id=row.deposit_id,
                business_id=row.business_id,
                plan=str(plan),
                paid_until=paid_until_dt,
                currency=row.currency,
                amount_minor=int(row.amount_minor or 0),
                status="success",
                dispatched=False,
                meta={"source": "deposit_initiate", "deposit_id": row.deposit_id, **(row.meta or {})},
            )
            db.add(sub)
            await db.commit()
            await db.refresh(sub)

        else:
            # Unknown payment type
            raise HTTPException(status_code=400, detail=f"unsupported_payment_type_{ptype}")

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

        token_payload = getattr(request.state, "token_payload", {}) or {}
        token_initiator_id = token_payload.get("sub") or token_payload.get("service") or token_payload.get("iss")
        token_initiator_role = token_payload.get("role")
        initiator_id = getattr(payload, "initiator_id", None) or token_initiator_id
        initiator_role = getattr(payload, "initiator_role", None) or token_initiator_role
        # Enforce non-nullable payout_type (msme | affiliate)
        payout_type = getattr(payload, "payout_type", None) or (payload.metadata or {}).get("payout_type")
        if not payout_type:
            raise HTTPException(status_code=400, detail="missing_payout_type")
        pt = str(payout_type).lower()

        # Pre-create related records depending on payout_type
        if pt == "msme":
            # require order_id or deposit_id to derive platform fee / msme cut
            deposit_ref = (payload.metadata or {}).get("deposit_id")
            deposit_row = None
            if deposit_ref:
                deposit_row = (await db.execute(select(PawaPayDeposit).where(PawaPayDeposit.deposit_id == deposit_ref))).scalar_one_or_none()

            if not payload.order_id and not deposit_row:
                raise HTTPException(status_code=400, detail="msme_payout_requires_order_or_deposit_id")

            # If deposit row exists, create MSME payout record using its computed fees
            if deposit_row:
                msme_rec = MSMEPayoutRecord(
                    order_id=deposit_row.order_id or payload.order_id,
                    business_id=deposit_row.business_id or payload.business_id,
                    payout_id=payout_id,
                    order_amount_minor=int(deposit_row.amount_minor or 0),
                    platform_fee_minor=int(deposit_row.platform_fee_minor or 0),
                    msme_payout_minor=int(deposit_row.msme_net_minor or 0),
                    status="pending",
                    meta={"source": "payout_initiate", "deposit_id": deposit_row.deposit_id, **(payload.metadata or {})},
                )
                db.add(msme_rec)
                await db.commit()
                await db.refresh(msme_rec)

        elif pt == "affiliate":
            # create AffiliatePayoutRecord for affiliate-engine driven payouts
            md = payload.metadata or {}
            batch_id = md.get("batch_id") or str(uuid.uuid4())
            epoch_id = md.get("epoch_id") or md.get("epoch")
            affiliate_id = md.get("affiliate_id") or md.get("affiliate")
            aff_rec = AffiliatePayoutRecord(
                payout_id=payout_id,
                batch_id=batch_id,
                epoch_id=epoch_id or "",
                affiliate_id=affiliate_id or "",
                amount_minor=int(payload.amount_minor or 0),
                currency=str(payload.currency).upper(),
                status="PENDING",
                meta={"source": "payout_initiate", **(payload.metadata or {})},
            )
            db.add(aff_rec)
            await db.commit()
            await db.refresh(aff_rec)

        row = PawaPayPayout(
            payout_id=payout_id,
            order_id=payload.order_id,
            business_id=payload.business_id,
            currency=str(payload.currency).upper(),
            amount_minor=int(payload.amount_minor),
            phone_number=normalized_phone,
            provider=provider,
            status="CREATED",
            meta={"request": payload.model_dump(mode="json"), "correlation_id": correlation_id, **(payload.metadata or {}), "initiator_id": initiator_id, "initiator_role": initiator_role},
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

        token_payload = getattr(request.state, "token_payload", {}) or {}
        token_initiator_id = token_payload.get("sub") or token_payload.get("service") or token_payload.get("iss")
        token_initiator_role = token_payload.get("role")
        initiator_id = getattr(payload, "initiator_id", None) or token_initiator_id
        initiator_role = getattr(payload, "initiator_role", None) or token_initiator_role

        row = PawaPayRefund(
            refund_id=refund_id,
            deposit_id=payload.deposit_id,
            order_id=payload.order_id,
            business_id=payload.business_id,
            currency=str(currency).upper(),
            amount_minor=int(payload.amount_minor or 0),
            status="CREATED",
            meta={"request": payload.model_dump(mode="json"), "correlation_id": correlation_id, **(payload.metadata or {}), "initiator_id": initiator_id, "initiator_role": initiator_role},
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

    # Compute and persist refund's platform_fee_minor (pro-rata) before committing.
    try:
        refunded_amt = int(amount_minor or 0)
    except Exception:
        refunded_amt = 0

    pf_for_refund = 0
    if refunded_amt and row.deposit_id:
        orig = (await db.execute(select(PawaPayDeposit).where(PawaPayDeposit.deposit_id == str(row.deposit_id)))).scalar_one_or_none()
        if orig and int(getattr(orig, "amount_minor", 0) or 0) > 0:
            try:
                pf_for_refund = int((int(getattr(orig, "platform_fee_minor", 0) or 0) * int(refunded_amt)) // int(getattr(orig, "amount_minor", 0) or 1))
            except Exception:
                pf_for_refund = 0
    logger.info("computed_refund_platform_fee", extra={"refund_id": refund_id, "deposit_id": row.deposit_id, "refunded_amt": refunded_amt, "pf_for_refund": pf_for_refund})

    # Persist computed platform_fee_minor on the refund row for revenue accounting.
    try:
        row.platform_fee_minor = int(pf_for_refund or 0)
    except Exception:
        row.platform_fee_minor = 0
    logger.info("persisted_refund_platform_fee", extra={"refund_id": refund_id, "platform_fee_minor": int(row.platform_fee_minor or 0)})

    # Always persist the callback update quickly, even if outbox insert is a duplicate.
    await db.commit()

    # If this refund references an original deposit, attempt to adjust recorded platform fee
    try:
        # prefer an explicit refund id in callback body if present
        refund_ref = body.get("refundId") or body.get("id") or deposit_id
        orig_dep_id = row.deposit_id or (body.get("depositId") if body.get("depositId") else None)
        if orig_dep_id:
            orig = (await db.execute(select(PawaPayDeposit).where(PawaPayDeposit.deposit_id == str(orig_dep_id)))).scalar_one_or_none()
            if orig:
                try:
                    refunded_amt = int(amount_minor or 0)
                except Exception:
                    refunded_amt = 0
                if refunded_amt and int(orig.amount_minor or 0) > 0 and int(getattr(orig, "platform_fee_minor", 0) or 0) > 0:
                    # Pro-rate platform fee reduction by refund fraction
                    try:
                        reduction = int((int(orig.platform_fee_minor) * refunded_amt) // int(orig.amount_minor))
                    except Exception:
                        reduction = 0
                    orig.platform_fee_minor = max(0, int(orig.platform_fee_minor) - int(reduction))
                    orig.meta = {**(orig.meta or {}), "platform_fee_adjusted": True, "platform_fee_adjustment": int(reduction), "adjusted_by_refund": refund_ref}
                    logger.info("adjusted_original_platform_fee", extra={"original_deposit_id": orig.deposit_id, "reduction": int(reduction), "orig_platform_fee_after": int(orig.platform_fee_minor)})
                    orig.updated_at = _utcnow()
                    await db.commit()
    except Exception:
        logger.exception("refund_adjust_platform_fee_failed", extra={"refund_id": refund_ref})

    # Dispatch to order-delivery immediately if we have an order_id and payment succeeded
    correlation_id = getattr(request.state, "correlation_id", None) or request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    logger.warning(f"CALLBACK_PROCESSING: deposit={deposit_id}, status={status}, order_id={row.order_id}, will_dispatch={status == 'COMPLETED' and bool(row.order_id)}")
    if status == "COMPLETED" and row.order_id:
        try:
            logger.warning(f"DISPATCHING_TO_ORDER_DELIVERY: order_id={row.order_id}")
            await _dispatch_to_order_delivery(order_id=str(row.order_id), correlation_id=correlation_id)
            logger.warning(f"DISPATCH_SUCCESS: order_id={row.order_id}")
        except Exception as e:
            # Don't fail the callback if dispatch fails - outbox will retry
            logger.warning(f"DISPATCH_FAILED: order_id={row.order_id}, error={str(e)}")

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

        # try to extract provider transaction id for better tracing
        _prov_tx = None
        if isinstance(body.get("providerTransactionId"), str):
            _prov_tx = body.get("providerTransactionId")
        else:
            _pt = body.get("providerTransaction") if isinstance(body.get("providerTransaction"), dict) else {}
            _prov_tx = _pt.get("id") or _pt.get("providerTransactionId") or body.get("providerTransactionId")

        payload_event = {
            "event_id": f"deposit-{deposit_id}",
            "event_type": "pawapay_deposit",
            "occurred_at": _utcnow().isoformat().replace("+00:00", "Z"),
            "correlation_id": correlation_id,
            "producer": "payment-revenue",
            "deposit_id": deposit_id,
            "status": status,
            "amount": _minor_to_major(int(amount_minor or 0)),
            "amount_minor": int(amount_minor or 0),
            "currency": currency,
            "phone_number": row.phone_number,
            "provider": row.provider,
            "provider_transaction_id": _prov_tx,
            "platform_fee_minor": int(getattr(row, "platform_fee_minor", 0) or 0),
            "fee_bps": int(getattr(row, "fee_bps", 0)) if getattr(row, "fee_bps", None) is not None else None,
            "payment_type": getattr(row, "payment_type", None),
            "msme_net_minor": int(getattr(row, "msme_net_minor", 0) or 0),
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
            # Fallback: if we have an order_id or business_id (subscription flow), assume msme-engine.
            try:
                meta_source = (row.meta or {}).get("source")
                if row.order_id or row.business_id or meta_source == "msme-subscribe":
                    target_base = get_msme_base_url().rstrip("/")
            except Exception:
                target_base = None

        occurred_at_iso = payload_event.get("occurred_at")

        if not target_base:
            # No clear initiator — do not broadcast; only create notification outbox (already handled).
            target_base = None

        if target_base:
            if status == "COMPLETED":
                # Persist provider tx id and fee info on the deposit row for bookkeeping
                try:
                    req_meta = (row.meta or {}).get("request") if (row.meta or {}) else {}
                except Exception:
                    req_meta = {}
                # derive msme_net_minor and platform_fee_minor if missing
                try:
                    msme_from_meta = int(req_meta.get("msmeNetMinor") or req_meta.get("msme_net_minor") or row.msme_net_minor or 0)
                except Exception:
                    msme_from_meta = int(getattr(row, "msme_net_minor", 0) or 0)
                try:
                    platform_fee_from_meta = int((row.meta or {}).get("platform_fee_minor") or req_meta.get("platform_fee_minor") or (int(row.amount_minor or 0) - int(msme_from_meta)))
                except Exception:
                    platform_fee_from_meta = int(getattr(row, "platform_fee_minor", 0) or 0)
                try:
                    fee_bps_from_meta = int((row.meta or {}).get("fee_bps") or req_meta.get("fee_bps") or req_meta.get("transaction_fee_bps"))
                except Exception:
                    fee_bps_from_meta = getattr(row, "fee_bps", None)
                # write back to row
                row.provider_transaction_id = _prov_tx
                row.platform_fee_minor = int(platform_fee_from_meta or 0)
                row.fee_bps = int(fee_bps_from_meta) if fee_bps_from_meta is not None else None
                row.payment_type = getattr(row, "payment_type", None) or req_meta.get("paymentType") or req_meta.get("payment_type")
                row.msme_net_minor = int(msme_from_meta or 0)
                row.updated_at = _utcnow()
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
                # create subscription payment row when applicable
                try:
                    if str(row.payment_type or "").lower() == "subscription":
                        existing_sub = (await db.execute(select(SubscriptionPayment).where(SubscriptionPayment.payment_id == deposit_id))).scalar_one_or_none()
                        if not existing_sub:
                            paid_until = _utcnow() + timedelta(days=30)
                            sp = SubscriptionPayment(payment_id=deposit_id, business_id=row.business_id, plan="paid", paid_until=paid_until, currency=row.currency, amount_minor=int(row.amount_minor or 0), meta={**(row.meta or {})})
                            db.add(sp)
                            await db.commit()
                except Exception:
                    logger.exception("create_subscription_payment_failed", extra={"deposit_id": deposit_id})
                # Build a minimal success event for the initiator.
                paid_until = (_utcnow() + timedelta(days=30)).isoformat().replace("+00:00", "Z")
                initiator_event = {
                    "event_id": f"deposit-{deposit_id}",
                    "event_type": "payment_success",
                    "occurred_at": occurred_at_iso,
                    "correlation_id": correlation_id,
                    "producer": "payment-revenue",
                    "payment_id": deposit_id,
                    "depositId": deposit_id,
                    "amount_minor": int(row.amount_minor or amount_minor or 0),
                    "order_id": str(row.order_id) if row.order_id else None,
                    "business_id": str(row.business_id) if row.business_id else None,
                    "amount": _minor_to_major(int(row.amount_minor or amount_minor or 0)),
                    "currency": currency,
                    "plan": "paid",
                    "paid_until": paid_until,
                    "meta": (row.meta or {}),
                    "provider": row.provider,
                    "provider_transaction_id": _prov_tx,
                    "platform_fee_minor": int(getattr(row, "platform_fee_minor", 0) or 0),
                    "fee_bps": int(getattr(row, "fee_bps", 0)) if getattr(row, "fee_bps", None) is not None else None,
                    "payment_type": getattr(row, "payment_type", None),
                    "msme_net_minor": int(getattr(row, "msme_net_minor", 0) or 0),
                }
                
                # Send a unified callback to the initiating service. Use a single
                # endpoint for deposit callbacks so initiators can implement one handler.
                dest = f"{target_base}/callbacks/payments/deposits"
                try:
                    from libs.outbox.schemas import PawapayDepositInitiator

                    payload_validated = PawapayDepositInitiator(**initiator_event).model_dump()
                except Exception:
                    payload_validated = initiator_event

                await create_outbox_row(
                    db,
                    "pawapay_deposit_initiator",
                    payload_validated,
                    destination=dest,
                    idempotency_key=f"deposit:{deposit_id}:initiator",
                    correlation_id=correlation_id,
                    producer="payment-revenue",
                )
            else:
                initiator_event = {
                    "event_id": f"deposit-{deposit_id}",
                    "event_type": "payment_failed",
                    "occurred_at": occurred_at_iso,
                    "correlation_id": correlation_id,
                    "producer": "payment-revenue",
                    "payment_id": deposit_id,
                    "depositId": deposit_id,
                    "amount_minor": int(row.amount_minor or amount_minor or 0),
                    "order_id": str(row.order_id) if row.order_id else None,
                    "business_id": str(row.business_id) if row.business_id else None,
                    "amount": _minor_to_major(int(row.amount_minor or amount_minor or 0)),
                    "currency": currency,
                    "failure_code": row.failure_code,
                    "failure_message": row.failure_message,
                    "meta": (row.meta or {}),
                    "provider": row.provider,
                    "provider_transaction_id": _prov_tx,
                    "platform_fee_minor": int(getattr(row, "platform_fee_minor", 0) or 0),
                    "fee_bps": int(getattr(row, "fee_bps", 0)) if getattr(row, "fee_bps", None) is not None else None,
                    "payment_type": getattr(row, "payment_type", None),
                    "msme_net_minor": int(getattr(row, "msme_net_minor", 0) or 0),
                    "response": (row.meta or {}).get("callback") if (row.meta or {}) else body,
                }
                await create_outbox_row(
                    db,
                    "pawapay_deposit_initiator",
                    initiator_event,
                    destination=f"{target_base}/callbacks/payments/deposits",
                    idempotency_key=f"deposit:{deposit_id}:initiator_failed",
                    correlation_id=correlation_id,
                    producer="payment-revenue",
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
            try:
                from libs.outbox.schemas import NotificationPayload

                notif_valid = NotificationPayload(**notif_payload).model_dump()
            except Exception:
                notif_valid = notif_payload

            await create_outbox_row(
                db,
                "notification",
                notif_valid,
                destination=f"{base_notif}/notification/send",
                idempotency_key=str(payload_event["event_id"]),
                correlation_id=correlation_id,
                producer="payment-revenue",
            )

    try:
        await db.commit()
    except IntegrityError:
        # Most commonly duplicate outbox dedupe_key due to callback retries.
        await db.rollback()

    return {"ok": True}


def _require_internal_secret_pr(request: Request) -> None:
    expected = (get_outbox_flush_internal_secret() or "").strip()
    provided = (request.headers.get("X-Internal-Secret") or "").strip()
    if not expected or not provided or not secrets.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="invalid_internal_secret")


@app.get("/outbox/pending")
async def outbox_pending_pr(request: Request, batch_size: int = 50, db: AsyncSession = Depends(get_db_session)):
    _require_internal_secret_pr(request)
    sql = """
    SELECT id, topic, payload::text as payload, dedupe_key, destination, attempts, scheduled_at, correlation_id
    FROM public.outbox
    WHERE status = 'pending'
    ORDER BY created_at ASC
    LIMIT :limit
    """
    res = await db.execute(text(sql), {"limit": int(batch_size)})
    rows = res.fetchall()
    out = []
    for r in rows:
        try:
            payload = json.loads(r.payload) if r.payload else {}
        except Exception:
            payload = {}
        out.append({
            "id": str(r.id),
            "event_type": r.topic,
            "payload": payload,
            "dedupe_key": r.dedupe_key,
            "destination": r.destination,
            "attempts": int(r.attempts or 0),
            "scheduled_at": r.scheduled_at,
            "correlation_id": r.correlation_id,
        })
    return out


@app.post("/outbox/ack")
async def outbox_ack_pr(request: Request, body: 'OutboxAckRequest', db: AsyncSession = Depends(get_db_session)):
    _require_internal_secret_pr(request)
    ids = body.ids or []
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="invalid_ids")
    now = _utcnow()
    for _id in ids:
        await db.execute(text("UPDATE public.outbox SET status='sent', last_error=NULL, attempts = COALESCE(attempts,0) + 1, updated_at = :now WHERE id = :id"), {"id": _id, "now": now})
    await db.commit()
    return {"acked": ids}


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
            "provider_transaction_id": (body.get("providerTransactionId") or (body.get("providerTransaction") if isinstance(body.get("providerTransaction"), dict) else {}).get("id")),
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
            out_id = str(uuid.uuid4())
            await create_outbox_row(db, "notification", notif_payload, id=out_id, destination=f"{base_notif}/notification/send", idempotency_key=str(payload_event["event_id"]), producer="payment-revenue")
        # Also attempt to notify the initiating service directly with a concise event
        initiator_id = (row.meta or {}).get("initiator_id") or (row.meta or {}).get("initiator")
        initiator_role = (row.meta or {}).get("initiator_role")
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
            try:
                meta_source = (row.meta or {}).get("source")
                if row.order_id or row.business_id or meta_source == "msme-subscribe":
                    target_base = get_msme_base_url().rstrip("/")
            except Exception:
                target_base = None

        if target_base and status in _PAWAPAY_TERMINAL:
            occurred_at_iso = payload_event.get("occurred_at")
            # If this is a successful payout tied to an order, ensure settlement rows exist.
            if status == "COMPLETED" and row.order_id and row.business_id:
                try:
                    # Try to find an existing settlement for this order.
                    existing_settlement = (
                        await db.execute(select(Settlement).where(Settlement.order_id == str(row.order_id)))
                    ).scalar_one_or_none()
                    if not existing_settlement:
                        # Prefer bookkeeping info from the original deposit when available.
                        dep = (
                            await db.execute(
                                select(PawaPayDeposit)
                                .where(PawaPayDeposit.order_id == str(row.order_id))
                                .where(PawaPayDeposit.business_id == str(row.business_id))
                                .order_by(PawaPayDeposit.created_at.desc())
                                .limit(1)
                            )
                        ).scalar_one_or_none()

                        if dep:
                            fee_bps = int(getattr(dep, "fee_bps", 0) or 0)
                            platform_fee = int(getattr(dep, "platform_fee_minor", 0) or 0)
                            msme_net = int(getattr(dep, "msme_net_minor", 0) or 0)
                            payment_id = dep.deposit_id
                            metadata = {**(dep.meta or {}), "derived_from": "deposit_callback"}
                        else:
                            # Fallback: compute fee bps and platform fee from payout request meta
                            req_meta = (row.meta or {}).get("request") if (row.meta or {}) else {}
                            fee_bps, _ = await _get_fee_bps_for_business(business_id=row.business_id)
                            platform_fee = _fee_amount_minor_units(int(row.amount_minor or 0), int(fee_bps or 0))
                            share = get_affiliate_commission_share_of_platform_fee()
                            affiliate_commission = _round_share(int(platform_fee), share)
                            msme_net = int(row.amount_minor or 0) - int(platform_fee)
                            payment_id = req_meta.get("paymentId") if isinstance(req_meta, dict) else None
                            metadata = {**(req_meta or {}), "derived_from": "payout_callback"}

                        # Create settlement and payout ledger entries.
                        try:
                            share = get_affiliate_commission_share_of_platform_fee()
                            affiliate_commission = _round_share(int(platform_fee), share)
                            platform_net = int(platform_fee) - int(affiliate_commission)

                            s = Settlement(
                                order_id=str(row.order_id),
                                payment_id=str(payment_id) if payment_id else str(row.payout_id),
                                business_id=str(row.business_id),
                                currency=row.currency,
                                amount_minor=int(row.amount_minor or 0),
                                fee_bps=int(fee_bps or 0),
                                platform_fee_minor=int(platform_fee),
                                affiliate_commission_minor=int(affiliate_commission),
                                msme_net_minor=int(msme_net),
                                status="computed",
                                dispatched=False,
                                meta={**(metadata or {}), "occurred_at": occurred_at_iso},
                            )
                            db.add(s)
                            await db.commit()
                            await db.refresh(s)

                            payout_msme = Payout(
                                order_id=str(row.order_id),
                                payment_id=str(s.payment_id),
                                business_id=str(row.business_id),
                                payee_type="msme",
                                payee_id=str(row.business_id),
                                currency=row.currency,
                                amount_minor=int(msme_net),
                                status="pending",
                                meta={"settlement_id": s.id},
                            )
                            payout_affiliate = Payout(
                                order_id=str(row.order_id),
                                payment_id=str(s.payment_id),
                                business_id=str(row.business_id),
                                payee_type="affiliate",
                                payee_id=None,
                                currency=row.currency,
                                amount_minor=int(affiliate_commission),
                                status="pending",
                                meta={"settlement_id": s.id},
                            )
                            payout_platform = Payout(
                                order_id=str(row.order_id),
                                payment_id=str(s.payment_id),
                                business_id=str(row.business_id),
                                payee_type="platform",
                                payee_id=None,
                                currency=row.currency,
                                amount_minor=int(platform_net),
                                status="pending",
                                meta={"settlement_id": s.id},
                            )
                            db.add(payout_msme)
                            db.add(payout_affiliate)
                            db.add(payout_platform)
                            await db.commit()

                            # Dispatch side effects (order-delivery + affiliate engine)
                            await _dispatch_to_order_delivery(order_id=str(row.order_id), correlation_id=correlation_id)
                            affiliate_event = _build_affiliate_event(
                                event_id=f"settle-{s.id}",
                                correlation_id=correlation_id,
                                payment_id=s.payment_id,
                                order_id=s.order_id,
                                business_id=s.business_id,
                                user_phone=None,
                                amount_minor=int(s.amount_minor),
                                currency=s.currency,
                                msme_amount_minor=int(s.msme_net_minor),
                                affiliate_amount_minor=int(s.affiliate_commission_minor),
                                platform_amount_minor=int(s.platform_fee_minor) - int(s.affiliate_commission_minor),
                                affiliate_id=None,
                                affiliate_code=(s.meta.get("affiliate_code") if isinstance(s.meta, dict) else None),
                                occurred_at=occurred_at_iso,
                            )
                            await _dispatch_to_affiliate_engine(payload=affiliate_event, correlation_id=correlation_id)

                            # Mark dispatched
                            s.dispatched = True
                            s.status = "dispatched"
                            payout_msme.status = "dispatched"
                            payout_affiliate.status = "dispatched"
                            payout_platform.status = "dispatched"
                            await db.commit()
                        except Exception:
                            logger.exception("create_settlement_from_payout_failed", extra={"payout_id": row.payout_id, "order_id": row.order_id})
                except Exception:
                    logger.exception("ensure_settlement_on_payout_failed", extra={"payout_id": row.payout_id})
                if status == "COMPLETED":
                    initiator_event = {
                        "event_id": f"payout-{payout_id}",
                        "event_type": "payout_success",
                        "occurred_at": occurred_at_iso,
                        "correlation_id": correlation_id,
                        "producer": "payment-revenue",
                        "payment_id": payout_id,
                        "order_id": str(row.order_id) if row.order_id else None,
                        "business_id": str(row.business_id) if row.business_id else None,
                        "amount": _minor_to_major(int(row.amount_minor or amount_minor or 0)),
                        "currency": currency,
                        "meta": (row.meta or {}),
                        "provider": row.provider,
                        "provider_transaction_id": (body.get("providerTransactionId") or (body.get("providerTransaction") if isinstance(body.get("providerTransaction"), dict) else {}).get("id")),
                    }
                    out_id = str(uuid.uuid4())
                    await create_outbox_row(db, "pawapay_payout_initiator", initiator_event, id=out_id, destination=f"{target_base}/callbacks/payments/payouts", idempotency_key=f"payout:{payout_id}:initiator", producer="payment-revenue")
                else:
                    initiator_event = {
                        "event_id": f"payout-{payout_id}",
                        "event_type": "payout_failed",
                        "occurred_at": occurred_at_iso,
                        "correlation_id": correlation_id,
                        "producer": "payment-revenue",
                        "payment_id": payout_id,
                        "order_id": str(row.order_id) if row.order_id else None,
                        "business_id": str(row.business_id) if row.business_id else None,
                        "amount": _minor_to_major(int(row.amount_minor or amount_minor or 0)),
                        "currency": currency,
                        "failure_code": row.failure_code,
                        "failure_message": row.failure_message,
                        "meta": (row.meta or {}),
                        "provider": row.provider,
                        "provider_transaction_id": (body.get("providerTransactionId") or (body.get("providerTransaction") if isinstance(body.get("providerTransaction"), dict) else {}).get("id")),
                        "response": (row.meta or {}).get("callback") if (row.meta or {}) else body,
                    }
                    out_id = str(uuid.uuid4())
                    await create_outbox_row(db, "pawapay_payout_initiator", initiator_event, id=out_id, destination=f"{target_base}/callbacks/payments/payouts", idempotency_key=f"payout:{payout_id}:initiator_failed", producer="payment-revenue")

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
        # extract provider transaction id when available
        _prov_tx = None
        if isinstance(body.get("providerTransactionId"), str):
            _prov_tx = body.get("providerTransactionId")
        else:
            _pt = body.get("providerTransaction") if isinstance(body.get("providerTransaction"), dict) else {}
            _prov_tx = _pt.get("id") or _pt.get("providerTransactionId") or body.get("providerTransactionId")

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
                "provider_transaction_id": _prov_tx,
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
            await create_outbox_row(
                db,
                "notification",
                notif_payload,
                destination=f"{base_notif}/notification/send",
                idempotency_key=str(payload_event["event_id"]),
                producer="payment-revenue",
            )

        # Notify initiator service directly about refund outcome
        initiator_id = (row.meta or {}).get("initiator_id") or (row.meta or {}).get("initiator")
        initiator_role = (row.meta or {}).get("initiator_role")
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
            try:
                meta_source = (row.meta or {}).get("source")
                if row.order_id or row.business_id or meta_source == "msme-subscribe":
                    target_base = get_msme_base_url().rstrip("/")
            except Exception:
                target_base = None

        if target_base:
            occurred_at_iso = payload_event.get("occurred_at")
            if status == "COMPLETED":
                initiator_event = {
                    "event_id": f"refund-{refund_id}",
                    "event_type": "refund_success",
                    "occurred_at": occurred_at_iso,
                    "correlation_id": correlation_id,
                    "producer": "payment-revenue",
                    "refund_id": refund_id,
                    "order_id": str(row.order_id) if row.order_id else None,
                    "business_id": str(row.business_id) if row.business_id else None,
                    "amount": _minor_to_major(int(row.amount_minor or amount_minor or 0)),
                    "currency": currency,
                    "meta": (row.meta or {}),
                    "provider_transaction_id": _prov_tx,
                }
                await create_outbox_row(
                    db,
                    "pawapay_refund_initiator",
                    initiator_event,
                    destination=f"{target_base}/callbacks/payments/refunds",
                    idempotency_key=f"refund:{refund_id}:initiator",
                    correlation_id=correlation_id,
                    producer="payment-revenue",
                )
            else:
                initiator_event = {
                    "event_id": f"refund-{refund_id}",
                    "event_type": "refund_failed",
                    "occurred_at": occurred_at_iso,
                    "correlation_id": correlation_id,
                    "producer": "payment-revenue",
                    "refund_id": refund_id,
                    "order_id": str(row.order_id) if row.order_id else None,
                    "business_id": str(row.business_id) if row.business_id else None,
                    "amount": _minor_to_major(int(row.amount_minor or amount_minor or 0)),
                    "currency": currency,
                    "failure_code": row.failure_code,
                    "failure_message": row.failure_message,
                    "meta": (row.meta or {}),
                    "provider_transaction_id": _prov_tx,
                    "response": (row.meta or {}).get("callback") if (row.meta or {}) else body,
                }
                await create_outbox_row(
                    db,
                    "pawapay_refund_initiator",
                    initiator_event,
                    destination=f"{target_base}/callbacks/payments/refunds",
                    idempotency_key=f"refund:{refund_id}:initiator_failed",
                    correlation_id=correlation_id,
                    producer="payment-revenue",
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
