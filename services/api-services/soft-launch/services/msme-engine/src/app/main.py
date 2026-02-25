from __future__ import annotations

import logging
import secrets
import time
import uuid
import os
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_FLOOR
from typing import Optional, Any
import asyncio
import httpx

# Best-effort: load .env file when present (optional dependency: python-dotenv)
try:
    from dotenv import load_dotenv, find_dotenv

    env_path = find_dotenv()
    if env_path:
        load_dotenv(env_path, override=False)
        logging.getLogger(__name__).info(f"Loaded env file: {env_path}")
except Exception:
    # Do nothing if python-dotenv is not available or loading fails
    pass

from fastapi import FastAPI, Request, Depends, HTTPException, Response, Header
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, text, or_
from sqlalchemy import Table, MetaData, Column, String, Integer, DateTime, JSON, func, update
import re
from sqlalchemy.exc import IntegrityError
from prometheus_client import Counter, Histogram, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
from prometheus_client import multiprocess
from sqlalchemy.ext.asyncio import AsyncSession


def ensure_multiproc_dir() -> str | None:
    """Return `PROMETHEUS_MULTIPROC_DIR` if set and ensure directory exists.

    Returns None when not set or on error.
    """
    mp_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not mp_dir:
        return None
    try:
        os.makedirs(mp_dir, exist_ok=True)
        return mp_dir
    except Exception:
        return None

from src.app.db import get_db_session, engine
from src.app.config import (
    get_pg_schema,
    get_notification_base_url,
    get_notification_timeout_seconds,
    get_jwt_secret,
    get_payment_revenue_base_url,
    get_subscription_price_minor,
    get_subscription_currency,
)
from src.app import audit_client
from src.app.models import (
    Base,
    Business,
    BusinessSubscription,
    MsmeCode,
    PaymentInitiation,
    OutboxEvent,
    Role,
    User,
    AuthSession,
    VerificationToken,
    MsmeEvent,
)
from src.app.schemas import (
    AuthLogin,
    AuthRegister,
    BusinessMetadataOut,
    BusinessEntitlementsOut,
    BusinessOut,
    BusinessPhoneLookupOut,
    DeliveryLocationsUpdate,
    BusinessRegister,
    BusinessRegisterOut,
    BusinessUpdate,
    LogoutRequest,
    MsmeEventOut,
    PaymentFailedEvent,
    PaymentSuccessEvent,
    RefreshRequest,
    SubscribeRequest,
    SubscribeAndPayRequest,
    SubscriptionInitiateOut,
    SubscriptionPriceUpdate,
    DefaultSubscriptionPriceUpdate,
    DefaultSubscriptionPriceOut,
    SubscriptionOut,
    TokenPair,
    UserLookupOut,
    UserPhoneLookupOut,
    UserOut,
    UserUpdate,
    PaymentCallback,
    OutboxAckRequest,
    MSMEOnboardRequest,
    AffiliateOnboardRequest,
)
from src.app.security import (
    get_current_user,
    get_user_and_role,
    hash_password,
    issue_access_token,
    issue_refresh_token,
    jwt_decode,
    verify_password,
)
from src.app.idempotency import idempotent_execute, scope_for
import asyncio

try:
    # background reminder job (best-effort import; tests may not need DB)
    from src.app.jobs import subscription_reminder
except Exception:
    subscription_reminder = None

app = FastAPI(title="MSME Engine (Soft Launch)")

logger = logging.getLogger("msme_engine")

_SERVICE = "msme-engine"

# Forward important Python logs (WARNING+) to audit-service.
audit_client.install_audit_log_forwarding(service=_SERVICE)


def init_sentry() -> None:
    """Initialize Sentry if `SENTRY_DSN` is set; no-op otherwise.

    This provides a safe local fallback when a project-level wrapper
    isn't available or the `sentry-sdk` package is not installed.
    """
    try:
        import importlib
        sentry_sdk = importlib.import_module("sentry_sdk")

        dsn = os.environ.get("SENTRY_DSN") or os.environ.get("SENTRY_DSN_URL")
        if not dsn:
            return
        traces = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0"))
        sentry_sdk.init(dsn=dsn, traces_sample_rate=traces)
        logger.info("sentry_initialized")
    except Exception:
        # Best-effort: do not raise on missing package or invalid config.
        logger.exception("sentry_init_failed_local")

def _expires_at_from_exp_ts(exp_ts) -> datetime:
    """Normalize JWT `exp` claim value to a timezone-aware datetime.

    Accepts int/float or numeric strings. Raises HTTPException on missing/invalid values.
    """
    if exp_ts is None:
        raise HTTPException(status_code=500, detail="token_missing_exp")
    if isinstance(exp_ts, str):
        try:
            exp_int = int(float(exp_ts))
        except Exception:
            raise HTTPException(status_code=500, detail="invalid_token_exp")
    elif isinstance(exp_ts, (int, float)):
        exp_int = int(exp_ts)
    else:
        raise HTTPException(status_code=500, detail="unsupported_token_exp_type")
    return datetime.fromtimestamp(exp_int, tz=timezone.utc)


_PLAN_FREE = "free"
_PLAN_PAID = "paid"


def _normalize_billing_interval(value: str | None) -> str:
    v = (value or "monthly").strip().lower()
    return "yearly" if v == "yearly" else "monthly"


def _compute_periods_paid(amount_minor: int | None, unit_price_minor: int | None) -> Decimal:
    if not amount_minor or not unit_price_minor or int(unit_price_minor) <= 0:
        return Decimal("0")
    return Decimal(int(amount_minor)) / Decimal(int(unit_price_minor))


def _compute_paid_through(start_at: datetime, periods_paid: Decimal, interval: str) -> datetime:
    whole_periods = int(periods_paid.to_integral_value(rounding=ROUND_FLOOR))
    remainder = periods_paid - Decimal(whole_periods)
    days_per_period = 365 if interval == "yearly" else 30
    base = start_at + timedelta(days=(whole_periods * days_per_period))
    extra_days = int((remainder * Decimal(days_per_period)).to_integral_value(rounding=ROUND_FLOOR))
    return base + timedelta(days=extra_days)


def _normalize_zmb_provider(provider: str | None) -> str | None:
    if not provider:
        return None
    raw = provider.strip()
    if not raw:
        return None

    upper = raw.upper()
    # Accept official pawaPay provider codes
    if upper in {"AIRTEL_OAPI_ZMB", "MTN_MOMO_ZMB", "ZAMTEL_ZMB"}:
        return upper

    # Accept common short-hands
    if upper in {"AIRTEL", "AIRTEL_ZMB"}:
        return "AIRTEL_OAPI_ZMB"
    if upper in {"MTN", "MTN_ZMB"}:
        return "MTN_MOMO_ZMB"
    if upper in {"ZAMTEL", "ZAMTEL_ZMB"}:
        return "ZAMTEL_ZMB"

    # If caller passes a generic gateway label, omit provider and let payment-revenue infer.
    if upper in {"PAWA", "PAWAPAY", "PAWA_PAY", "PAWA-PAY"}:
        return None

    # Unknown provider value
    raise HTTPException(status_code=400, detail="invalid_provider")


async def _notify_in_app(*, db: AsyncSession | None = None, user_id: str | None, business_id: str | None, template: str, payload: dict | None, correlation_id: str | None) -> None:
    """Emit an in-app notification.

    If a DB session is provided, write a canonical Outbox row so the outbox
    dispatcher delivers the notification asynchronously. If no DB session is
    available, fall back to the previous best-effort HTTP POST.
    """
    # Attempt outbox write when DB session is available.
    if db is not None:
        try:
            from src.app.helpers.outbox.outbox import create_outbox_row
            from src.app.helpers.outbox.schemas import NotificationPayload

            dest_base = get_notification_base_url().rstrip("/")
            target = f"{dest_base}/notification/send"

            model = NotificationPayload(
                channel="in_app",
                user_id=user_id,
                business_id=business_id,
                template=template,
                payload=payload or {},
            )

            out_id = str(uuid.uuid4())
            await create_outbox_row(db, "notification_send", model.model_dump(), id=out_id, destination=target, correlation_id=correlation_id, idempotency_key=out_id, producer="msme-engine")
            try:
                await db.commit()
            except Exception:
                # If commit fails, swallow the error to keep notifications best-effort.
                await db.rollback()
        except Exception:
            logger.info("notification_outbox_failed", extra={"template": template, "correlation_id": correlation_id})
        return

    # Fallback: direct HTTP call (best-effort)
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
        # Best-effort: do not fail core flows if notification service is down.
        logger.info("notification_unreachable", extra={"template": template, "correlation_id": correlation_id})


def _normalize_plan(value: str | None) -> str:
    v = (value or "").strip().lower()
    if v in ("", _PLAN_FREE):
        return _PLAN_FREE
    if v == _PLAN_PAID:
        return _PLAN_PAID
    raise HTTPException(status_code=400, detail="invalid_subscription_plan")


def _is_subscription_active(plan: str, expiry: datetime | None) -> bool:
    if plan != _PLAN_PAID:
        return True
    if expiry is None:
        # Paid with no expiry is treated as active.
        return True
    now = datetime.now(timezone.utc)
    return expiry >= now


def _effective_plan_for(b: Business) -> str:
    plan = _normalize_plan(b.subscription_plan)
    if not bool(b.is_active):
        return _PLAN_FREE
    if plan == _PLAN_PAID and not _is_subscription_active(plan, b.subscription_expiry):
        return _PLAN_FREE
    return plan


def _entitlements_for(b: Business) -> BusinessEntitlementsOut:
    plan = _effective_plan_for(b)
    is_active = bool(b.is_active)

    # Policy:
    # - Free: bots enabled, no affiliate promo links, 7% fee
    # - Paid: bots enabled, affiliate promo links enabled, 5% fee
    if plan == _PLAN_PAID and is_active:
        return BusinessEntitlementsOut(
            business_id=b.id,
            plan=_PLAN_PAID,
            subscription_expiry=b.subscription_expiry,
            is_active=is_active,
            bot_instances_enabled=True,
            affiliate_promo_links_enabled=True,
            transaction_fee_pct=0.05,
        )

    return BusinessEntitlementsOut(
        business_id=b.id,
        plan=_PLAN_FREE,
        subscription_expiry=b.subscription_expiry,
        is_active=is_active,
        bot_instances_enabled=True,
        affiliate_promo_links_enabled=False,
        transaction_fee_pct=0.07,
    )


@app.post("/callbacks/payments/payouts")
async def pawapay_payout_callback(payload: PaymentCallback, db: AsyncSession = Depends(get_db_session)):
    """Receive payout callback from payment-revenue.

    Request model: `PaymentCallback` (see `src.app.schemas.PaymentCallback`).

    Example:
    {
        "event_type": "payout.created",
        "event_id": "evt_123",
        "depositId": "dep_456",
        "business_id": "biz_789",
        "amount_minor": 10000,
        "currency": "ZMW",
        "status": "completed"
    }

    This endpoint is intentionally lightweight for soft-launch: it logs
    the payload and returns 200 to allow outbox delivery to succeed.
    """
    logger.info("pawapay_payout_callback_received", extra={"payload": payload.model_dump()})
    return {"ok": True}


@app.post("/callbacks/notifications/delivery")
async def notification_delivery_callback(request: Request, db: AsyncSession = Depends(get_db_session)):
    """Receive delivery receipts or notification responses from the central
    notification service. Records a local MsmeEvent and returns 200.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    logger.info("notification_delivery_callback_received", extra={"payload": body})

    try:
        await _record_event(
            db=db,
            event_id=f"notification_callback:{uuid.uuid4().hex}",
            event_type="notification_callback",
            business_id=body.get("business_id"),
            source=body.get("source") or "notification_service",
            correlation_id=request.headers.get("X-Correlation-Id"),
            meta=body,
        )
    except Exception:
        logger.exception("record_notification_callback_failed")

    return {"ok": True}


@app.post("/callbacks/payments/deposits")
async def deposit_callback(payload: PaymentCallback, request: Request, db: AsyncSession = Depends(get_db_session)):
    """Unified deposit callback.

    - Records an MsmeEvent
    - Correlates and updates PaymentInitiation
    - Updates subscription tables (Business, BusinessSubscription)
    - Emits notifications to business owner (in-app + whatsapp) and admin (email)
    - Writes canonical pawapay outbox row
    - Emits `msme_referral` outbox to affiliate engine
    """
    p = payload.model_dump()
    logger.info("deposit_callback_received", extra={"payload": p})

    # Record a generic event for observability and downstream automation.
    try:
        await _record_event(
            db=db,
            event_id=payload.event_id or f"deposit_callback:{uuid.uuid4().hex}",
            event_type=(payload.event_type or "deposit_callback"),
            business_id=payload.business_id,
            source="payment_revenue",
            correlation_id=request.headers.get("X-Correlation-Id"),
            meta=p,
        )
    except Exception:
        logger.exception("record_deposit_callback_failed")

    # Identify deposit and status
    deposit_id = p.get("depositId") or p.get("payment_id") or p.get("id")
    status = (p.get("event_type") or p.get("status") or "").lower()
    success = any(s in status for s in ("completed", "success", "payment_success", "deposit_success"))

    initiation = None
    if deposit_id:
        try:
            res = await db.execute(select(PaymentInitiation).where(PaymentInitiation.deposit_id == str(deposit_id)))
            initiation = res.scalar_one_or_none()
            if initiation:
                initiation.status = "completed" if success else "failed"
                await db.commit()
        except Exception:
            logger.exception("update_payment_initiation_failed", extra={"deposit_id": deposit_id})

    # Update subscription tables on successful payment
    if initiation and success:
        try:
            business_id = initiation.business_id
            now = datetime.now(timezone.utc)
            amount_minor = (initiation.meta.get("amount_minor") if initiation and isinstance(initiation.meta, dict) else p.get("amount_minor") or p.get("amount"))
            # Determine plan: prefer initiation.meta.plan, then payload.plan, default to paid
            plan_candidate = None
            if initiation and isinstance(initiation.meta, dict):
                plan_candidate = initiation.meta.get("plan")
            if plan_candidate is None and isinstance(p, dict):
                plan_candidate = p.get("plan")
            if not plan_candidate:
                plan_candidate = _PLAN_PAID
            # Normalize and resolve unit price for the plan
            try:
                plan_candidate = _normalize_plan(plan_candidate)
            except Exception:
                # If normalization fails, fallback to paid
                plan_candidate = _PLAN_PAID
            unit_price = get_subscription_price_minor(plan_candidate)
            periods = _compute_periods_paid(amount_minor, unit_price)
            if periods > 0:
                paid_through = _compute_paid_through(now, periods, "monthly")

                # Update Business record
                try:
                    business_rec = (await db.execute(select(Business).where(Business.id == business_id))).scalar_one_or_none()
                    if business_rec:
                        business_rec.subscription_plan = "paid"
                        business_rec.subscription_expiry = paid_through
                        business_rec.is_active = True
                        await db.commit()
                except Exception:
                    logger.exception("update_business_subscription_failed", extra={"business_id": business_id})

                # Upsert BusinessSubscription
                try:
                    subs = (await db.execute(select(BusinessSubscription).where(BusinessSubscription.business_id == business_id))).scalar_one_or_none()
                    if subs:
                        subs.plan = "paid"
                        subs.start_date = now
                        subs.end_date = paid_through
                        subs.status = "active"
                        db.add(subs)
                    else:
                        db.add(
                            BusinessSubscription(
                                business_id=business_id,
                                plan="paid",
                                start_date=now,
                                end_date=paid_through,
                                status="active",
                            )
                        )
                    await db.commit()
                except Exception:
                    logger.exception("upsert_business_subscription_failed", extra={"business_id": business_id})
        except Exception:
            logger.exception("update_subscription_failed")

    # Emit notifications via notification outbox: whatsapp+email to owner, email to admins
    try:
        from src.app.helpers.outbox.outbox import emit_notification

        business_id = (initiation.business_id if initiation else p.get("business_id"))
        note_payload = {"status": "completed" if success else "failed", "deposit_id": deposit_id, "metadata": p}

        # Fetch business owner id
        owner_user = None
        try:
            if business_id:
                business_rec = (await db.execute(select(Business).where(Business.id == business_id))).scalar_one_or_none()
                if business_rec and getattr(business_rec, "owner_id", None):
                    owner_user = (await db.execute(select(User).where(User.id == business_rec.owner_id))).scalar_one_or_none()
        except Exception:
            logger.exception("fetch_business_owner_failed", extra={"business_id": business_id})

        # WhatsApp to owner (best-effort)
        try:
            if owner_user:
                base = (get_notification_base_url() or "http://127.0.0.1:8570").rstrip("/")
                target = f"{base}/notification/send"
                await emit_notification(db, "whatsapp", user_id=owner_user.id, business_id=business_id, payload={**(note_payload or {}), "destination": target})
        except Exception:
            logger.exception("notify_owner_whatsapp_failed", extra={"business_id": business_id})

        # Email to owner
        try:
            if owner_user:
                owner_email_payload = {"subject": "Payment deposit", "body": f"Deposit {deposit_id} for your business {business_id} is {'completed' if success else 'failed'}.", "metadata": p}
                base = (get_notification_base_url() or "http://127.0.0.1:8570").rstrip("/")
                target = f"{base}/notification/send"
                await emit_notification(db, "email", user_id=owner_user.id, business_id=business_id, payload={**owner_email_payload, "destination": target})
        except Exception:
            logger.exception("notify_owner_email_failed", extra={"business_id": business_id})

        # Email admins
        try:
            res = await db.execute(select(User).join(Role, User.role_id == Role.id).where(Role.name == "admin"))
            admins = res.scalars().all()
            for admin in admins:
                try:
                    admin_payload = {"subject": "Payment deposit notification", "body": f"Deposit {deposit_id} for business {business_id} status: {'completed' if success else 'failed'}", "metadata": p}
                    base = (get_notification_base_url() or "http://127.0.0.1:8570").rstrip("/")
                    target = f"{base}/notification/send"
                    await emit_notification(db, "email", user_id=admin.id, business_id=None, payload={**admin_payload, "destination": target})
                except Exception:
                    logger.exception("notify_admin_failed", extra={"admin": getattr(admin, 'id', None)})
        except Exception:
            logger.exception("notify_admins_failed")
    except Exception:
        logger.exception("emit_notification_outbox_failed")


    # Emit referral-style event for affiliate consumers
    try:
        referral_base = os.environ.get("AFFILIATE_ENGINE_BASE_URL", "http://127.0.0.1:8510").rstrip("/")
        referral_target = f"{referral_base}/events/msme/referral"
        amount_minor = (initiation.meta.get("amount_minor") if initiation and isinstance(initiation.meta, dict) else p.get("amount_minor") or p.get("amount"))
        try:
            amount_zmw = float(amount_minor) / 100.0 if amount_minor is not None else None
        except Exception:
            amount_zmw = None

        # Resolve affiliate id from initiation, business record, or incoming payload
        business_affiliate_id = None
        business_id_for_lookup = None
        try:
            business_id_for_lookup = (initiation.business_id if initiation else p.get('business_id'))
            if business_id_for_lookup:
                business_rec = (await db.execute(select(Business).where(Business.id == business_id_for_lookup))).scalar_one_or_none()
                if business_rec and getattr(business_rec, "affiliate_id", None):
                    business_affiliate_id = business_rec.affiliate_id
        except Exception:
            logger.exception("fetch_business_failed", extra={"business_id": business_id_for_lookup})

        affiliate_id_val = None
        if initiation and getattr(initiation, "affiliate_id", None):
            affiliate_id_val = initiation.affiliate_id
        elif business_affiliate_id:
            affiliate_id_val = business_affiliate_id
        else:
            affiliate_id_val = p.get("affiliate_id")

        referral_payload = {
            "event_id": f"msme-referral-{uuid.uuid4().hex}",
            "event_type": "msme_referral",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "deposit_id": deposit_id,
            "affiliate_id": affiliate_id_val,
            "business_id": (initiation.business_id if initiation else p.get('business_id')),
            "amount_zmw": amount_zmw,
            "correlation_id": str(uuid.uuid4()),
            "meta": {"source": "msme-engine-outbox", "note": "referral from deposit flow"},
        }

        # Do not attempt to emit referral events when there is no deposit id.
        deposit_for_emit = referral_payload.get("deposit_id")
        if not deposit_for_emit or not isinstance(deposit_for_emit, str):
            logger.info("skip_emit_referral_missing_deposit_id", extra={"event_id": referral_payload.get("event_id"), "deposit_id": deposit_for_emit})
        else:
            from src.app.helpers.outbox.outbox import emit_msme_referral
            logger.info("about_to_emit_msme_outbox", extra={"topic": "msme_referral", "destination": referral_target, "dedupe_key": referral_payload.get("event_id"), "payload": referral_payload})
            # Retry once on transient failures to improve delivery reliability.
            sent = False
            for attempt in range(2):
                try:
                    # Parse occurred_at safely: accept ISO strings (with Z or offset) or None
                    raw_occurred = referral_payload.get("occurred_at")
                    occurred_dt = None
                    if isinstance(raw_occurred, str) and raw_occurred:
                        try:
                            s = raw_occurred
                            if s.endswith("Z"):
                                s = s[:-1] + "+00:00"
                            occurred_dt = datetime.fromisoformat(s)
                            if occurred_dt.tzinfo is None:
                                occurred_dt = occurred_dt.replace(tzinfo=timezone.utc)
                        except Exception:
                            logger.exception("parse_referral_occurred_at_failed", extra={"raw": raw_occurred})

                    # Coerce affiliate and business ids to strings (affiliate may be None)
                    aff = referral_payload.get("affiliate_id")
                    biz = referral_payload.get("business_id")
                    try:
                        aff_val = str(aff) if aff is not None else ""
                    except Exception:
                        aff_val = ""
                    try:
                        biz_val = str(biz) if biz is not None else ""
                    except Exception:
                        biz_val = ""

                    await emit_msme_referral(
                        db,
                        deposit_id=str(deposit_for_emit),
                        affiliate_id=aff_val,
                        business_id=biz_val,
                        amount_zmw=referral_payload.get("amount_zmw"),
                        occurred_at=occurred_dt,
                        meta=referral_payload.get("meta"),
                        dedupe_key=referral_payload.get("event_id"),
                        correlation_id=referral_payload.get("correlation_id"),
                        commit=True,
                    )
                    sent = True
                    break
                except Exception:
                    logger.exception("emit_referral_outbox_attempt_failed", extra={"attempt": attempt, "event_id": referral_payload.get("event_id")})
                    try:
                        await asyncio.sleep(0.1)
                    except Exception:
                        pass
            if not sent:
                logger.error("emit_referral_outbox_failed_after_retries", extra={"event_id": referral_payload.get("event_id")})
    except Exception:
        logger.exception("forward_to_affiliate_outbox_failed")

    return {"ok": True}



class _NoopMetric:
    def __init__(self, *_, **__):
        pass

    def labels(self, *_, **__):
        return self

    def inc(self, *_, **__):
        return None

    def observe(self, *_, **__):
        return None


try:
    _REQ_COUNT = Counter("http_requests_total", "Total HTTP requests", ["service", "method", "route", "status"])
    _REQ_LATENCY = Histogram("http_request_duration_seconds", "HTTP request duration", ["service", "method", "route"])
except ValueError:
    # Running under pytest or when module imported multiple times can trigger
    # duplicate timeseries registration in the global CollectorRegistry.
    # Fall back to no-op metric objects so tests and repeated imports don't fail.
    _REQ_COUNT = _NoopMetric()
    _REQ_LATENCY = _NoopMetric()



def _get_internal_secret() -> str | None:
    # Prefer unified env var, fall back to service config if present
    import os

    s = os.environ.get("OUTBOX_INTERNAL_SECRET")
    if s:
        return s
    # No config set for local dev: return a known test secret so local
    # integration tests can call internal endpoints without setting env.
    return "test-internal-secret"


async def _retry_db_call(coro_factory, retries: int = 3, base_delay: float = 0.2):
    """Run a DB coroutine factory with a small retry on deadlock errors.

    `coro_factory` should be a zero-arg callable that returns a coroutine (e.g. ``lambda: db.execute(...)``).
    """
    import asyncio
    from sqlalchemy.exc import DBAPIError

    for attempt in range(retries):
        try:
            return await coro_factory()
        except DBAPIError as e:
            msg = str(getattr(e, "__cause__", e) or "").lower()
            if "deadlock detected" in msg and attempt < retries - 1:
                await asyncio.sleep(base_delay * (2 ** attempt))
                continue
            raise

def _require_internal_secret(request: Request) -> None:
    """
    Validate the `X-Internal-Secret` header is set and matches the expected secret.

    Raises a 401 error if the secret is invalid or missing.
    """

    expected = (_get_internal_secret() or "").strip()
    provided = (request.headers.get("X-Internal-Secret") or "").strip()
    if not expected or not provided or not secrets.compare_digest(expected, provided):
        try:
            logger.info("internal_secret_invalid", extra={"path": request.url.path, "provided_present": bool(provided), "expected_configured": bool(expected)})
        except Exception:
            # best-effort logging only
            pass
        raise HTTPException(status_code=401, detail="invalid_internal_secret")


def _validate_schema_name(name: str) -> str:
    """Return the schema name if it matches a safe SQL identifier pattern.

    Raises ValueError if the name is invalid. This prevents injection via
    interpolated schema/table identifiers used when constructing driver SQL.
    """
    if not isinstance(name, str):
        raise ValueError("invalid schema")
    # strict SQL identifier pattern: starts with letter/underscore, then letters/digits/underscore
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        return name
    raise ValueError("invalid schema name")


def validate_external_payload(model_cls, payload: dict, *, logger_extra: dict | None = None):
    """Validate `payload` against `model_cls` (a Pydantic model class).

    Returns the validated model instance or raises HTTPException(400) on error
    while logging details for observability.
    """
    try:
        return model_cls(**(payload or {}))
    except Exception as e:
        try:
            logger.warning("invalid_external_payload", extra={"model": getattr(model_cls, "__name__", str(model_cls)), **(logger_extra or {})})
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="invalid_payload")


@app.get("/outbox/pending")
async def outbox_pending(request: Request, batch_size: int = 50, db: AsyncSession = Depends(get_db_session)):
    _require_internal_secret(request)
    now = datetime.now(timezone.utc)
    # Read from the service schema outbox_events table so the outbox-dispatcher
    # can request pending events for this service specifically.
    from src.app.config import get_pg_schema
    schema = _validate_schema_name(get_pg_schema())
    metadata = MetaData()
    outbox = Table(
        "outbox_events",
        metadata,
        Column("id", String),
        Column("topic", String),
        Column("destination", String),
        Column("target", String),
        Column("payload", JSON),
        Column("dedupe_key", String),
        Column("attempts", Integer),
        Column("scheduled_at", DateTime(timezone=True)),
        Column("correlation_id", String),
        Column("status", String),
        Column("created_at", DateTime(timezone=True)),
        schema=schema,
    )

    stmt = (
        select(
            outbox.c.id,
            outbox.c.topic,
            func.coalesce(outbox.c.destination, outbox.c.target).label("destination"),
            outbox.c.payload,
            func.coalesce(outbox.c.dedupe_key, outbox.c.topic).label("dedupe_key"),
            outbox.c.attempts,
            outbox.c.scheduled_at,
            outbox.c.correlation_id,
        )
        .where(outbox.c.status == "pending")
        .order_by(outbox.c.created_at)
        .limit(int(batch_size))
    )

    res = await _retry_db_call(lambda: db.execute(stmt))
    rows = [] if res is None else res.fetchall()
    out = []
    for r in rows:
        _id, topic, destination, payload_json, dedupe_key, attempts, scheduled_at, correlation_id = r
        # payload may already be a python object depending on driver; ensure it's a dict
        # payload may already be a python object depending on driver; ensure it's a dict
        payload = payload_json if isinstance(payload_json, dict) else (json.loads(payload_json) if payload_json else {})
        out.append({
            "id": _id,
            "event_type": topic,
            "payload": payload,
            "dedupe_key": dedupe_key,
            "destination": destination,
            "attempts": attempts or 0,
            "scheduled_at": scheduled_at.isoformat() if scheduled_at is not None else None,
            "correlation_id": correlation_id,
        })
    return out


@app.post("/internal/notifications/broadcast/all")
async def broadcast_notification_all(request: Request, payload: dict, db: AsyncSession = Depends(get_db_session)):
    """Create notification outbox events for all users.

    Body schema (example):
    {
      "channel": "email",
      "template": "promo_2026",
      "payload": {"subject": "Hello", "body": "..."}
    }
    """
    _require_internal_secret(request)
    try:
        from src.app.helpers.outbox.outbox import emit_notification
        from src.app.helpers.outbox.schemas import NotificationPayload as _NotificationPayload

        notif = _NotificationPayload(**payload)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_payload")

    try:
        # fetch all user ids
        res = await db.execute(select(User.id))
        user_ids = [r[0] for r in res.fetchall()]
    except Exception:
        raise HTTPException(status_code=500, detail="fetch_users_failed")

    created = []
    for uid in user_ids:
        try:
            out_id = await emit_notification(db, notif.channel, user_id=uid, payload=notif.payload, dedupe_key=None, correlation_id=str(uuid.uuid4()), commit=False)
            created.append(str(out_id))
        except Exception:
            logger.exception("emit_notification_failed", extra={"user_id": uid})

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="commit_failed")

    return {"count": len(created), "ids": created}


@app.post("/internal/notifications/broadcast/role/{role_name}")
async def broadcast_notification_role(role_name: str, request: Request, payload: dict, db: AsyncSession = Depends(get_db_session)):
    """Create notification outbox events for users with a specific role."""
    _require_internal_secret(request)
    try:
        from src.app.helpers.outbox.outbox import emit_notification
        from src.app.helpers.outbox.schemas import NotificationPayload as _NotificationPayload

        notif = _NotificationPayload(**payload)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_payload")

    try:
        res = await db.execute(select(User).join(Role, User.role_id == Role.id).where(Role.name == role_name))
        users = res.scalars().all()
    except Exception:
        raise HTTPException(status_code=500, detail="fetch_role_users_failed")

    created = []
    for u in users:
        try:
            out_id = await emit_notification(db, notif.channel, user_id=u.id, payload=notif.payload, dedupe_key=None, correlation_id=str(uuid.uuid4()), commit=False)
            created.append(str(out_id))
        except Exception:
            logger.exception("emit_notification_failed", extra={"user_id": getattr(u, 'id', None)})

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="commit_failed")

    return {"role": role_name, "count": len(created), "ids": created}


@app.post("/internal/notifications/broadcast/user/{user_id}")
async def broadcast_notification_user(user_id: str, request: Request, payload: dict, db: AsyncSession = Depends(get_db_session)):
    """Create a notification outbox event for a specific user."""
    _require_internal_secret(request)
    try:
        from src.app.helpers.outbox.outbox import emit_notification
        from src.app.helpers.outbox.schemas import NotificationPayload as _NotificationPayload

        notif = _NotificationPayload(**payload)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_payload")

    try:
        out_id = await emit_notification(db, notif.channel, user_id=user_id, payload=notif.payload, dedupe_key=None, correlation_id=str(uuid.uuid4()), commit=True)
    except Exception:
        logger.exception("emit_notification_failed", extra={"user_id": user_id})
        raise HTTPException(status_code=500, detail="emit_failed")

    return {"user_id": user_id, "id": str(out_id)}


@app.get("/internal/businesses")
async def internal_businesses(request: Request, db: AsyncSession = Depends(get_db_session)):
    """Return list of businesses with owner phone and location (internal use).

    Secured by `X-Internal-Secret` header.
    """
    _require_internal_secret(request)

    res = await _retry_db_call(lambda: db.execute(select(Business, User).join(User, Business.owner_id == User.id)))
    rows = [] if res is None else res.all()
    out = []
    for b, owner in rows:
        out.append({
            "id": b.id,
            "name": b.name,
            "phone": owner.phone,
            "location": b.location,
        })
    return out


@app.get("/internal/affiliates")
async def internal_affiliates(request: Request, db: AsyncSession = Depends(get_db_session)):
    """Return list of affiliate users (name, phone).

    Secured by `X-Internal-Secret` header.
    """
    _require_internal_secret(request)

    res = await _retry_db_call(lambda: db.execute(select(User).join(Role, User.role_id == Role.id).where(Role.name == "affiliate")))
    users = [] if res is None else res.scalars().all()
    out = []
    for u in users:
        out.append({"id": u.id, "name": u.username, "phone": u.phone})
    return out



@app.post("/outbox/ack")
async def outbox_ack(request: Request, body: OutboxAckRequest, db: AsyncSession = Depends(get_db_session)):
    """Acknowledge delivery of Outbox events.

    Request model: `OutboxAckRequest` (see `src.app.schemas.OutboxAckRequest`).

    Example:
    {
        "ids": ["out_1", "out_2"]
    }

    This endpoint requires the internal secret header `X-Internal-Secret`.
    """
    _require_internal_secret(request)
    ids = body.ids or []
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="invalid_ids")
    acked = []
    now = datetime.now(timezone.utc)
    from src.app.config import get_pg_schema
    schema = _validate_schema_name(get_pg_schema())
    metadata = MetaData()
    outbox = Table(
        "outbox_events",
        metadata,
        Column("id", String),
        Column("status", String),
        Column("created_at", DateTime(timezone=True)),
        Column("updated_at", DateTime(timezone=True)),
        schema=schema,
    )

    for _id in ids:
        try:
            stmt = (
                update(outbox)
                .where(outbox.c.id == _id)
                .values(status="sent", updated_at=now)
            )
            await _retry_db_call(lambda: db.execute(stmt))
            acked.append(_id)
        except Exception:
            logger.exception("outbox_ack_update_failed", extra={"id": _id})
    await db.commit()
    return {"acked": acked}


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    start = time.perf_counter()
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    try:
        response = await call_next(request)
    except asyncio.CancelledError:
        try:
            logger.info("request_cancelled", extra={"method": request.method, "path": request.url.path, "correlation_id": correlation_id})
        except Exception:
            pass
        # Client disconnected / request cancelled. Return a short response to avoid noisy stack traces.
        resp = Response(status_code=499, content="client_closed_request")
        resp.headers["X-Correlation-Id"] = correlation_id
        return resp
    response.headers["X-Correlation-Id"] = correlation_id

    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    _REQ_COUNT.labels(_SERVICE, request.method, route_path, str(response.status_code)).inc()
    _REQ_LATENCY.labels(_SERVICE, request.method, route_path).observe(time.perf_counter() - start)

    logger.info("request", extra={"method": request.method, "path": route_path, "status": response.status_code, "correlation_id": correlation_id})
    return response


async def startup() -> None:
    # Initialize Sentry early (best-effort)
    try:
        init_sentry()
    except Exception:
        logger.exception("sentry_init_during_startup_failed")

    async with engine.begin() as conn:
        schema = _validate_schema_name(get_pg_schema())
        # ensure per-service schema exists and set search_path so create_all runs in that schema
        try:
            # schema name validated by _validate_schema_name above; driver SQL used
            await conn.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            await conn.exec_driver_sql(f"SET search_path TO {schema}, public")
        except Exception:
            # best-effort: continue and let create_all fail noisily if this DB doesn't support schemas
            pass
        # For in-memory SQLite used in tests, ensure tables are created on the
        # underlying sync engine as well so they are visible across
        # connections (shared-cache URI handled in `create_engine`). This
        # provides a reliable test experience when TestClient triggers
        # startup and then opens request connections.
        try:
            from src.app.config import get_database_url

            if get_database_url().startswith("sqlite+aiosqlite:///:memory:"):
                # create tables synchronously on the sync engine
                Base.metadata.create_all(bind=engine.sync_engine)
            else:
                await conn.run_sync(Base.metadata.create_all)
        except Exception:
            # Best-effort: fall back to async create_all
            try:
                await conn.run_sync(Base.metadata.create_all)
            except Exception:
                logger.exception("create_all_failed")

    async for db in get_db_session():
        await _ensure_default_roles(db)

    # Fail fast when running in production with missing critical secrets
    try:
        from src.app.config import get_required_secret

        # will raise in production if missing
        get_required_secret("MSME_JWT_SECRET", hint="Use your secrets manager and set MSME_JWT_SECRET env")
    except Exception:
        logger.exception("required_secret_missing")
        # Re-raise so service fails to start rather than silently running insecurely
        raise

    # Start background reminder loop if available. Run as best-effort.
    if subscription_reminder is not None:
        try:
            # create a background task that runs periodic checks
            app.state._subscription_reminder_task = asyncio.create_task(
                subscription_reminder.background_loop(get_db_session, app)
            )
        except Exception:
            logger.exception("failed_starting_subscription_reminder")

    # Initialize observability integrations (best-effort)
    try:
        init_sentry()
    except Exception:
        logger.exception("sentry_init_failed")


# Register startup handler without using the deprecated decorator.
app.add_event_handler("startup", startup)


async def shutdown() -> None:
    # No-op shutdown wrapper for test compatibility.
    return None

@app.post("/internal/debug/sentry-test")
async def _internal_debug_sentry_test(request: Request):
    """Internal-only endpoint to trigger a server exception so Sentry integration can be validated.

    Requires `X-Internal-Secret` header.
    """
    _require_internal_secret(request)
    raise Exception("sentry_test_exception")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/_debug/env")
async def _debug_env():
    """Temporary debug endpoint to inspect environment variables locally."""
    return {"OUTBOX_INTERNAL_SECRET": os.getenv("OUTBOX_INTERNAL_SECRET")}


@app.get("/metrics")
async def metrics():
    # Support Prometheus multiprocess mode when `PROMETHEUS_MULTIPROC_DIR` is set.
    mp_dir = ensure_multiproc_dir()
    if mp_dir:
        try:
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            data = generate_latest(registry)
            return Response(content=data, media_type=CONTENT_TYPE_LATEST)
        except Exception:
            logger.exception("metrics_multiprocess_failed")
            # fallback to single-process generation
            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


async def _ensure_default_roles(db: AsyncSession) -> None:
    existing = (await db.execute(select(Role.name))).scalars().all()
    existing_set = set(existing)
    defaults = [
        ("admin", "Platform admin"),
        ("affiliate", "Affiliate / contributor"),
        ("msme", "MSME owner"),
        ("staff", "Internal staff"),
        ("default", "Default user"),
        ("freeter", "Freeter / downgraded user"),
    ]
    created = False
    for name, desc in defaults:
        if name in existing_set:
            continue
        db.add(Role(name=name, description=desc))
        created = True
    if created:
        await db.commit()


async def _role_id_for(db: AsyncSession, role_name: str) -> str:
    role = (await db.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
    if role:
        return role.id

    role = Role(name=role_name, description=None)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role.id


def _user_out(user: User, role_name: str) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        role=role_name,
        business_id=user.business_id,
        affiliate_id=user.affiliate_id,
        is_active=bool(user.is_active),
        signed_terms=bool(getattr(user, "signed_terms", False)),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _business_out(b: Business) -> BusinessOut:
    return BusinessOut(
        id=b.id,
        name=b.name,
        owner_id=b.owner_id,
        location=b.location,
        category=b.category,
        logo_url=b.logo_url,
        affiliate_id=b.affiliate_id,
        referred_by_msme_code=b.referred_by_msme_code,
        subscription_plan=b.subscription_plan,
        subscription_expiry=b.subscription_expiry,
        delivery_locations=b.delivery_locations,
        tags=b.tags,
        is_active=bool(b.is_active),
        created_at=b.created_at,
        updated_at=b.updated_at,
    )


def _subscription_out(s: BusinessSubscription) -> SubscriptionOut:
    return SubscriptionOut(
        id=s.id,
        business_id=s.business_id,
        plan=s.plan,
        start_date=s.start_date,
        end_date=s.end_date,
        status=s.status,
        created_at=s.created_at,
    )


async def _generate_msme_code(db: AsyncSession) -> str:
    # Format: MSME-xxxxx
    for _ in range(12):
        code = f"MSME-{secrets.randbelow(100000):05d}"
        exists = (await db.execute(select(MsmeCode).where(MsmeCode.code == code))).scalar_one_or_none()
        if not exists:
            return code
    raise HTTPException(status_code=500, detail="msme_code_generation_failed")


async def _record_event(
    *,
    db: AsyncSession,
    event_id: str,
    event_type: str,
    business_id: Optional[str],
    source: Optional[str],
    correlation_id: Optional[str],
    meta: Optional[dict],
) -> None:
    # Events are intentionally disabled in this build. This no-op keeps
    # existing call sites functional without recording lifecycle events.
    return None


# ---- Auth ----


@app.post("/auth/register", response_model=UserOut)
async def auth_register(
    payload: AuthRegister,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    """
    Register a new user.

    This endpoint is idempotent; if the client retries the request due to a
    network error, the server will ensure that only one user is created.

    Args:
        payload (AuthRegister): containing the user's registration details.
        response (Response): the response object to set the status code and body.
        db (AsyncSession): the database session to use for the operation.
        x_idempotency_key (Optional[str]): the idempotency key to use for the operation.

    Returns:
        A tuple containing the status code and the response body.
    """
    async def _run():
        role_id = await _role_id_for(db, payload.role)
        user = User(
            username=payload.username,
            email=str(payload.email),
            phone=payload.phone,
            password_hash=hash_password(payload.password),
            role_id=role_id,
            is_active=True,
        )
        db.add(user)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=409, detail="user_already_exists")

        await db.refresh(user)
        return 201, _user_out(user, payload.role)

    status, body = await idempotent_execute(db=db, scope=scope_for("POST", "/auth/register"), key=x_idempotency_key, run=_run)
    response.status_code = int(status)
    return body


@app.post("/auth/login", response_model=TokenPair)
async def auth_login(payload: AuthLogin, db: AsyncSession = Depends(get_db_session)):
    
    """
    Login a user and return a token pair containing an access token and a refresh token.

    If the user is not found or the provided password is incorrect, return a 401 response.

    The refresh token is persisted as a revocable session and can be used to obtain a new access token when the existing one expires.

    Args:
        payload (AuthLogin): containing the user's login details.

    Returns:
        A tuple containing the access token and the refresh token.
    """
    identifier = payload.identifier.strip()
    # Use `.scalars().first()` to defensively handle duplicate rows instead of
    # raising `MultipleResultsFound` — prefer the first matching user.
    user = (
        await db.execute(
            select(User).where(or_(User.username == identifier, User.email == identifier, User.phone == identifier))
        )
    ).scalars().first()

    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")

    _, role_name = await get_user_and_role(db, user.id)

    refresh_token = issue_refresh_token(user=user, role_name=role_name)
    access_token = issue_access_token(user=user, role_name=role_name)

    # persist refresh token as a revocable session
    exp_ts = jwt_decode(refresh_token, secret=get_jwt_secret()).get("exp")
    expires_at = _expires_at_from_exp_ts(exp_ts)
    session = AuthSession(user_id=user.id, token=refresh_token, expires_at=expires_at)
    db.add(session)
    await db.commit()

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@app.post("/auth/refresh", response_model=TokenPair)
async def auth_refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db_session)):
    """
    Refresh an access token and rotate the refresh token for the user.

    The user is identified by the provided refresh token, which is verified
    against the stored revocable session. If the session is revoked, a 401
    response is returned.

    Args:
        payload (RefreshRequest): containing the refresh token to rotate.

    Returns:
        A tuple containing the new access token and the new refresh token.
    """
    token_payload = jwt_decode(payload.refresh_token, secret=get_jwt_secret())
    if token_payload.get("typ") != "refresh":
        raise HTTPException(status_code=401, detail="invalid_token")

    session = (
        await db.execute(select(AuthSession).where(AuthSession.token == payload.refresh_token))
    ).scalar_one_or_none()
    if not session or session.revoked:
        raise HTTPException(status_code=401, detail="session_revoked")


    user_id = token_payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="invalid_token_payload")
    user, role_name = await get_user_and_role(db, user_id)

    access_token = issue_access_token(user=user, role_name=role_name)
    refresh_token = issue_refresh_token(user=user, role_name=role_name)

    # rotate refresh token
    session.revoked = True
    exp_ts = jwt_decode(refresh_token, secret=get_jwt_secret()).get("exp")
    expires_at = _expires_at_from_exp_ts(exp_ts)
    db.add(AuthSession(user_id=user.id, token=refresh_token, expires_at=expires_at))
    await db.commit()

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@app.post("/auth/logout")
async def auth_logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db_session)):
    """
    Revoke a user's refresh token, effectively logging them out.

    Args:
        payload (LogoutRequest): containing the refresh token to revoke.

    Returns:
        A JSON response containing a single key-value pair: "status": "ok".
    """
    session = (
        await db.execute(select(AuthSession).where(AuthSession.token == payload.refresh_token))
    ).scalar_one_or_none()
    if not session:
        return {"status": "ok"}

    session.revoked = True
    await db.commit()
    return {"status": "ok"}


@app.post("/auth/service-token/business/{business_id}", response_model=TokenPair)
async def auth_service_token_business(business_id: str, db: AsyncSession = Depends(get_db_session)):
    """
    Issue service-to-service JWT token for a business without requiring login.
    
    This endpoint is designed for downstream services (bots, background jobs) that need
    to authenticate on behalf of a business without user credentials.
    
    **Security Note**: This endpoint should be protected by API gateway/firewall rules
    to prevent unauthorized access. Only internal services should be able to call this.
    """
    # Find business
    business = (await db.execute(select(Business).where(Business.id == business_id))).scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="business_not_found")
    
    if not business.is_active:
        raise HTTPException(status_code=403, detail="business_inactive")
    
    # Get the business owner (user) to generate token
    owner = (await db.execute(select(User).where(User.id == business.owner_id))).scalar_one_or_none()
    if not owner:
        raise HTTPException(status_code=404, detail="owner_not_found")
    
    if not owner.is_active:
        raise HTTPException(status_code=403, detail="owner_inactive")
    
    _, role_name = await get_user_and_role(db, owner.id)
    
    # Issue tokens for the owner (representing the business).
    # Ensure the access token contains the business id so service tokens can act on behalf of the business.
    owner.business_id = business.id
    refresh_token = issue_refresh_token(user=owner, role_name=role_name)
    access_token = issue_access_token(user=owner, role_name=role_name)
    
    # Persist refresh token as a revocable session
    exp_ts = jwt_decode(refresh_token, secret=get_jwt_secret()).get("exp")
    expires_at = _expires_at_from_exp_ts(exp_ts)
    session = AuthSession(user_id=owner.id, token=refresh_token, expires_at=expires_at)
    db.add(session)
    await db.commit()
    
    return TokenPair(access_token=access_token, refresh_token=refresh_token)

# Service-to-service JWT for user without login, for bots and background jobs that need to authenticate on behalf of a business without user credentials. This endpoint should be protected by API gateway/firewall rules to prevent unauthorized access. Only internal services should be able to call this.
@app.post("/auth/service-token/{user_id}", response_model=TokenPair)
async def auth_service_token(user_id: str, db: AsyncSession = Depends(get_db_session)):
    """Issue service-to-service JWT token for a user without requiring login.

    This endpoint is designed for downstream services (bots, background jobs) that need
    to authenticate on behalf of a user without user credentials.

    **Security Note**: This endpoint should be protected by API gateway/firewall rules
    to prevent unauthorized access. Only internal services should be able to call this.

    Args:
        user_id (str): The ID of the user to issue the token for.

    Returns:
        A tuple containing the access token and the refresh token.
    """
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="user_inactive")

    _, role_name = await get_user_and_role(db, user.id)

    refresh_token = issue_refresh_token(user=user, role_name=role_name)
    access_token = issue_access_token(user=user, role_name=role_name)

    # Persist refresh token as a revocable session
    exp_ts = jwt_decode(refresh_token, secret=get_jwt_secret()).get("exp")
    expires_at = _expires_at_from_exp_ts(exp_ts)
    session = AuthSession(user_id=user.id, token=refresh_token, expires_at=expires_at)
    db.add(session)
    await db.commit()

    return TokenPair(access_token=access_token, refresh_token=refresh_token)





@app.get("/auth/me", response_model=UserOut)
async def auth_me(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    """Fetch current user details, including associated business (if linked).

    The response includes the user's role name, which is either the default
    role name or the role name contained in the JWT token.

    Args:
        request (Request): The incoming request.
        user (User): The current user.
        db (AsyncSession): The database session.

    Returns:
        UserOut: The user details with associated business (if linked)."""
    role_name = "default"
    token_payload = getattr(request.state, "token_payload", None)
    if isinstance(token_payload, dict) and token_payload.get("role"):
        role_name = str(token_payload.get("role"))
    else:
        _, role_name = await get_user_and_role(db, user.id)

    return _user_out(user, role_name)


@app.get("/auth/phone/{user_phone}", response_model=UserPhoneLookupOut)
async def auth_phone_lookup(user_phone: str, db: AsyncSession = Depends(get_db_session)):
    """Lookup user by phone. Returns user details with associated business (if linked).
    
    Uses optimized left join to fetch user and business in single database query.
    """
    # Join User with Business (left join to get user even if no business)
    stmt = (
        select(User, Business)
        .outerjoin(Business, User.business_id == Business.id)
        .where(User.phone == user_phone)
    )
    
    result = (await db.execute(stmt)).one_or_none()
    if not result:
        raise HTTPException(status_code=404, detail="user_not_found")
    
    user, business = result
    _, role_name = await get_user_and_role(db, user.id)
    
    # Build business object if user is linked to a business
    business_out = None
    if business:
        business_out = _business_out(business)
    
    return UserPhoneLookupOut(
        user=UserOut(
            id=user.id,
            username=user.username,
            email=user.email,
            phone=user.phone,
            role=role_name,
            business_id=user.business_id,
            affiliate_id=user.affiliate_id,
            is_active=bool(user.is_active),
            signed_terms=bool(getattr(user, "signed_terms", False)),
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
        business=business_out,
    )


@app.put("/auth/user/{user_id}", response_model=UserOut)
async def auth_user_update(
    user_id: str,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="user_not_found")

        role_name = None
        if payload.role is not None:
            user.role_id = await _role_id_for(db, payload.role)
            role_name = payload.role

        if payload.username is not None:
            user.username = payload.username
        if payload.email is not None:
            user.email = str(payload.email)
        if payload.phone is not None:
            user.phone = payload.phone
        if payload.business_id is not None:
            user.business_id = payload.business_id
        if payload.affiliate_id is not None:
            # Normalize affiliate_id to string to match DB model
            try:
                user.affiliate_id = str(payload.affiliate_id)
            except Exception:
                user.affiliate_id = payload.affiliate_id
        if payload.is_active is not None:
            user.is_active = payload.is_active

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=409, detail="user_conflict")

        await db.refresh(user)
        if role_name is None:
            _, role_name = await get_user_and_role(db, user.id)

        return 200, _user_out(user, role_name)

    _, body = await idempotent_execute(db=db, scope=scope_for("PUT", "/auth/user/{user_id}"), key=x_idempotency_key, run=_run)
    return body


@app.delete("/auth/user/{user_id}")
async def auth_user_delete(
    user_id: str,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            return 200, {"status": "ok"}

        user.is_active = False
        await db.commit()
        return 200, {"status": "ok"}

    _, body = await idempotent_execute(db=db, scope=scope_for("DELETE", "/auth/user/{user_id}"), key=x_idempotency_key, run=_run)
    return body


@app.get("/auth/verify/{token}")
async def auth_verify(token: str, db: AsyncSession = Depends(get_db_session)):
    record = (await db.execute(select(VerificationToken).where(VerificationToken.token == token))).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="token_not_found")

    if record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="token_expired")

    return {"status": "verified"}


# ---- Business ----


@app.post("/business/register", response_model=BusinessRegisterOut)
async def business_register(
    request: Request,
    payload: BusinessRegister,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        if bool(payload.owner) == bool(payload.owner_user_id):
            raise HTTPException(status_code=400, detail="owner_required")

        owner_id: str
        if payload.owner_user_id:
            owner = (await db.execute(select(User).where(User.id == payload.owner_user_id))).scalar_one_or_none()
            if not owner:
                raise HTTPException(status_code=404, detail="owner_user_not_found")
            owner_id = owner.id
        else:
            # Narrow payload.owner for the type-checker and runtime safety
            owner_payload = payload.owner
            if owner_payload is None:
                raise HTTPException(status_code=400, detail="owner_required")

            role_id = await _role_id_for(db, "msme")
            owner = User(
                username=owner_payload.username,
                email=str(owner_payload.email),
                phone=owner_payload.phone,
                password_hash=hash_password(owner_payload.password),
                role_id=role_id,
                is_active=True,
            )
            db.add(owner)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                raise HTTPException(status_code=409, detail="owner_user_conflict")
            await db.refresh(owner)
            owner_id = owner.id

        # Create business (owner may be pre-existing or just created)
        business = Business(
            name=payload.name,
            owner_id=owner_id,
            location=payload.location,
            category=payload.category,
            logo_url=payload.logo_url,
            affiliate_id=(str(payload.affiliate_id) if payload.affiliate_id is not None else None),
            referred_by_msme_code=payload.referred_by_msme_code,
            subscription_plan=payload.subscription_plan,
            delivery_locations=payload.delivery_locations,
            tags=payload.tags,
            is_active=True,
        )
        db.add(business)
        await db.commit()
        await db.refresh(business)

        # Link user to business.
        owner = (await db.execute(select(User).where(User.id == owner_id))).scalar_one()
        owner.business_id = business.id
        await db.commit()

        code = await _generate_msme_code(db)
        db.add(MsmeCode(business_id=business.id, code=code))
        await db.commit()

        # Record a local lifecycle event for downstream automation.
        await _record_event(
            db=db,
            event_id=f"msme_registered:{business.id}:{uuid.uuid4().hex}",
            event_type="msme_registered",
            business_id=business.id,
            source="business_service",
            correlation_id=getattr(request.state, "correlation_id", None),
            meta={
                "affiliate_id": payload.affiliate_id,
                "referred_by_msme_code": payload.referred_by_msme_code,
            },
        )

        await _notify_in_app(
            db=db,
            user_id=owner_id,
            business_id=business.id,
            template="msme_registered",
            payload={"business_name": business.name, "msme_code": code},
            correlation_id=getattr(request.state, "correlation_id", None),
        )

        await audit_client.emit_audit(
            service="msme-engine",
            event_type="business_registered",
            payload={
                "business_id": business.id,
                "business_name": business.name,
                "msme_code": code,
                "owner_id": owner_id,
                "affiliate_id": payload.affiliate_id,
                "referred_by_msme_code": payload.referred_by_msme_code,
            },
            actor_id=owner_id,
            entity_type="business",
            entity_id=business.id,
            metadata={"correlation_id": getattr(request.state, "correlation_id", None)},
        )

        return 201, BusinessRegisterOut(business=_business_out(business), msme_code=code)

    status, body = await idempotent_execute(db=db, scope=scope_for("POST", "/business/register"), key=x_idempotency_key, run=_run)
    response.status_code = int(status)
    return body


@app.get("/business/{id}", response_model=BusinessOut)
async def business_get(id: str, db: AsyncSession = Depends(get_db_session)):
    b = (await db.execute(select(Business).where(Business.id == id))).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="business_not_found")
    return _business_out(b)


@app.put("/business/{id}", response_model=BusinessOut)
async def business_update(
    request: Request,
    id: str,
    payload: BusinessUpdate,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        b = (await db.execute(select(Business).where(Business.id == id))).scalar_one_or_none()
        if not b:
            raise HTTPException(status_code=404, detail="business_not_found")

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(b, field, value)

        await db.commit()
        await db.refresh(b)

        await _record_event(
            db=db,
            event_id=f"msme_updated:{b.id}:{uuid.uuid4().hex}",
            event_type="msme_updated",
            business_id=b.id,
            source="business_service",
            correlation_id=getattr(request.state, "correlation_id", None),
            meta=payload.model_dump(exclude_unset=True),
        )

        return 200, _business_out(b)

    _, body = await idempotent_execute(db=db, scope=scope_for("PUT", "/business/{id}"), key=x_idempotency_key, run=_run)
    return body


@app.delete("/business/{id}")
async def business_delete(
    request: Request,
    id: str,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        b = (await db.execute(select(Business).where(Business.id == id))).scalar_one_or_none()
        if not b:
            return 200, {"status": "ok"}

        b.is_active = False
        await db.commit()

        await _record_event(
            db=db,
            event_id=f"msme_suspended:{b.id}:{uuid.uuid4().hex}",
            event_type="msme_suspended",
            business_id=b.id,
            source="business_service",
            correlation_id=getattr(request.state, "correlation_id", None),
            meta=None,
        )

        return 200, {"status": "ok"}

    _, body = await idempotent_execute(db=db, scope=scope_for("DELETE", "/business/{id}"), key=x_idempotency_key, run=_run)
    return body


@app.post("/business/{id}/subscribe", response_model=SubscriptionInitiateOut)
async def business_subscribe(
    request: Request,
    id: str,
    payload: SubscribeRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    async def _run():
        b = (await db.execute(select(Business).where(Business.id == id))).scalar_one_or_none()
        if not b:
            raise HTTPException(status_code=404, detail="business_not_found")

        plan = _normalize_plan(payload.plan)

        # Free plan is immediate; paid requires payment_success event.
        sub_status = "active" if plan == _PLAN_FREE else "pending_payment"
        billing_interval = _normalize_billing_interval(getattr(payload, "billing_interval", None))
        sub = BusinessSubscription(business_id=b.id, plan=plan, billing_interval=billing_interval, status=sub_status)
        db.add(sub)
        await db.commit()
        await db.refresh(sub)

        if plan == _PLAN_FREE:
            b.subscription_plan = _PLAN_FREE
            b.subscription_expiry = None
            await db.commit()

        else:
            # record expected subscription price/currency on the business for paid plans
            try:
                b.subscription_plan = plan
                b.subscription_price_minor = get_subscription_price_minor(plan)
                b.subscription_currency = get_subscription_currency(plan)
                await db.commit()
            except Exception:
                logger.exception("set_subscription_price_failed")

            await _notify_in_app(
                db=db,
                user_id=b.owner_id,
                business_id=b.id,
                template="subscription_activated",
                payload={"plan": "free"},
                correlation_id=getattr(request.state, "correlation_id", None),
            )

        # Minimal payment initiation placeholder.
        payment_request = {
            "reference_id": sub.id,
            "business_id": b.id,
            "plan": plan,
            "currency": "ZMW",
        }
        await _record_event(
            db=db,
            event_id=f"subscription_initiated:{b.id}:{uuid.uuid4().hex}",
            event_type="subscription_initiated",
            business_id=b.id,
            source="business_service",
            correlation_id=getattr(request.state, "correlation_id", None),
            meta=payment_request,
        )

        await _record_event(
            db=db,
            event_id=f"subscription_initiated:{b.id}:{uuid.uuid4().hex}",
            event_type="subscription_initiated",
            business_id=b.id,
            source="business_service",
            correlation_id=getattr(request.state, "correlation_id", None),
            meta=payment_request,
        )

        await _notify_in_app(
            db=db,
            user_id=b.owner_id,
            business_id=b.id,
            template="subscription_initiated",
            payload=payment_request,
            correlation_id=getattr(request.state, "correlation_id", None),
        )

        return 201, SubscriptionInitiateOut(subscription=_subscription_out(sub), payment_request=payment_request)

    status, body = await idempotent_execute(db=db, scope=scope_for("POST", "/business/{id}/subscribe"), key=x_idempotency_key, run=_run)
    response.status_code = int(status)
    return body



@app.post("/business/{id}/subscribe_and_pay", response_model=SubscriptionInitiateOut)
async def business_subscribe_and_pay(
    request: Request,
    id: str,
    payload: SubscribeAndPayRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    """Subscribe and optionally initiate a deposit to payment-revenue.

    If `amount_minor` and `phone_number` are provided and the plan is paid,
    msme will call `payment-revenue`'s `/pawapay/deposits/initiate` and forward
    the caller's `Authorization` header (if present) so `payment-revenue` can
    record the initiator.
    """
    correlation_id = request.headers.get("X-Correlation-Id") or getattr(request.state, "correlation_id", None) or str(uuid.uuid4())

    async def _run():
        b = (await db.execute(select(Business).where(Business.id == id))).scalar_one_or_none()
        if not b:
            raise HTTPException(status_code=404, detail="business_not_found")

        plan = _normalize_plan(payload.plan)

        sub_status = "active" if plan == _PLAN_FREE else "pending_payment"
        # BusinessSubscription model does not accept a `status` kwarg; create
        # the subscription without the invalid argument and persist any
        # required status elsewhere if needed.
        sub = BusinessSubscription(business_id=b.id, plan=plan)
        # persist computed status on the subscription record
        try:
            sub.status = sub_status
        except Exception:
            # best-effort: if model doesn't accept status for any reason, continue
            pass
        db.add(sub)
        await db.commit()
        await db.refresh(sub)

        payment_request = {
            "reference_id": sub.id,
            "business_id": b.id,
            "plan": plan,
            "billing_interval": sub.billing_interval,
            "currency": payload.currency or "ZMW",
        }

        # Emit audit event for subscription initiation (immediately after creating subscription)
        try:
            await audit_client.emit_audit(
                service="msme-engine",
                event_type="subscription_initiated",
                payload=payment_request,
                actor_id=b.owner_id,
                entity_type="business",
                entity_id=b.id,
                metadata={"correlation_id": correlation_id},
            )
        except Exception:
            logger.exception("audit_emit_failed_subscription_initiated")

        # If caller provided payment details and plan is paid, call payment-revenue
        pr_result = None
        normalized_provider = _normalize_zmb_provider(payload.provider)
        if plan == _PLAN_PAID and payload.amount_minor and payload.phone_number:
            # Require caller Authorization header for payment-initiating flows so payment-revenue can record initiator.
            auth = request.headers.get("Authorization")
            if not auth:
                raise HTTPException(status_code=401, detail="authorization_required_for_payment")

            pr_base = get_payment_revenue_base_url().rstrip("/")
            headers: dict[str, str] = {"Authorization": auth}
            # Use X-Idempotency-Key if provided or provided deposit_id
            idem = payload.deposit_id or x_idempotency_key or sub.id
            if idem:
                headers["X-Idempotency-Key"] = idem

            # Persist provided amount on business (caller-provided amount overrides default plan price)
            try:
                if payload.amount_minor:
                    b.subscription_price_minor = int(payload.amount_minor)
                else:
                    b.subscription_price_minor = get_subscription_price_minor(plan)
                b.subscription_currency = payload.currency or get_subscription_currency(plan)
                b.subscription_plan = plan
                await db.commit()
            except Exception:
                logger.exception("persist_subscription_price_failed")

            body = {
                "depositId": payload.deposit_id or str(uuid.uuid4()),
                "order_id": None,
                "business_id": b.id,
                "amount_minor": int(payload.amount_minor) if payload.amount_minor else int(b.subscription_price_minor or 0),
                "currency": payload.currency or (b.subscription_currency or "ZMW"),
                "phoneNumber": payload.phone_number,
                "metadata": {"reference_id": sub.id, "source": "msme-subscribe"},
            }
            # Attach affiliate context if present in caller's JWT
            try:
                auth = request.headers.get("Authorization")
                affiliate_id = None
                if auth and auth.lower().startswith("bearer "):
                    token = auth.split()[1]
                    try:
                        tok = jwt_decode(token, secret=get_jwt_secret())
                        affiliate_id = tok.get("affiliate_id")
                        if affiliate_id is not None:
                            try:
                                affiliate_id = str(affiliate_id)
                            except Exception:
                                pass
                    except Exception:
                        affiliate_id = None

                if affiliate_id:
                    try:
                        body["metadata"]["affiliate_id"] = str(affiliate_id)
                    except Exception:
                        body["metadata"]["affiliate_id"] = affiliate_id

                # Persist payment initiation so callbacks can be correlated
                try:
                    deposit_id_local = body.get("depositId")
                    init = PaymentInitiation(
                        deposit_id=str(deposit_id_local),
                        business_id=b.id,
                        subscription_id=sub.id,
                        affiliate_id=affiliate_id,
                        metadata=body,
                        status="pending",
                    )
                    db.add(init)
                    await db.commit()
                except Exception:
                    logger.exception("persist_payment_initiation_failed")
            except Exception:
                # best-effort: don't fail flow if affiliate parsing/persist fails
                logger.exception("affiliate_extraction_failed")
            if normalized_provider:
                body["provider"] = normalized_provider

            # Instead of calling payment-revenue synchronously, emit a PaymentInitiation
            # and an OutboxEvent using the helper so the outbox dispatcher handles delivery.
            try:
                from src.app.helpers.payment_helpers import emit_subscription_deposit_request

                eid = await emit_subscription_deposit_request(
                    db=db,
                    business_id=b.id,
                    subscription_id=sub.id,
                    amount_minor=int(payload.amount_minor) if payload.amount_minor else int(b.subscription_price_minor or 0),
                    currency=payload.currency or (b.subscription_currency or "ZMW"),
                    phone=payload.phone_number,
                    correlation_id=correlation_id,
                    initiator_id=(request.headers.get("X-Idempotency-Key") or x_idempotency_key or sub.id),
                )
                pr_result = {"initiated_event_id": eid}
            except Exception:
                logger.exception("emit_subscription_deposit_request_failed")
                raise HTTPException(status_code=502, detail="payment_revenue_initiation_failed")

        await _record_event(
            db=db,
            event_id=f"subscription_initiated:{b.id}:{uuid.uuid4().hex}",
            event_type="subscription_initiated",
            business_id=b.id,
            source="business_service",
            correlation_id=correlation_id,
            meta=payment_request,
        )

        await _notify_in_app(
            db=db,
            user_id=b.owner_id,
            business_id=b.id,
            template="subscription_initiated",
            payload={**payment_request, "message": "Subscription started. Please complete payment if required."},
            correlation_id=correlation_id,
        )

        result = SubscriptionInitiateOut(subscription=_subscription_out(sub), payment_request=payment_request)
        
        # Attach payment-revenue response when available.
        if pr_result is not None:
            result.payment_request["payment_revenue_response"] = pr_result

            # Emit audit event for the payment attempt/result returned by payment-revenue
            try:
                await audit_client.emit_audit(
                    service="msme-engine",
                    event_type="subscription_payment_attempt",
                    payload={"payment_response": pr_result},
                    actor_id=b.owner_id,
                    entity_type="business",
                    entity_id=b.id,
                    metadata={"correlation_id": correlation_id},
                )
            except Exception:
                logger.exception("audit_emit_failed_payment_attempt")

        # Send immediate user-facing notification depending on payment outcome.
        try:
            if plan == _PLAN_FREE:
                await _notify_in_app(
                    db=db,
                    user_id=b.owner_id,
                    business_id=b.id,
                    template="subscription_activated",
                    payload={"plan": "free", "message": "Welcome — your free subscription is active!"},
                    correlation_id=correlation_id,
                )
            else:
                # Paid plan: if payment-revenue returned a completed status, confirm immediately.
                status_val = None
                if isinstance(pr_result, dict):
                    status_val = str(pr_result.get("status") or pr_result.get("status_code") or "").upper()

                if status_val == "COMPLETED":
                    await _notify_in_app(
                        db=db,
                        user_id=b.owner_id,
                        business_id=b.id,
                        template="subscription_payment_success",
                        payload={"plan": plan, "message": "Congratulations — payment received and subscription is active."},
                        correlation_id=correlation_id,
                    )
                    # Emit audit: payment succeeded
                    try:
                        await audit_client.emit_audit(
                            service="msme-engine",
                            event_type="payment_success",
                            payload={"plan": plan, "payment_response": pr_result},
                            actor_id=b.owner_id,
                            entity_type="business",
                            entity_id=b.id,
                            metadata={"correlation_id": correlation_id},
                        )
                    except Exception:
                        logger.exception("audit_emit_failed_payment_success")
                else:
                    await _notify_in_app(
                        db=db,
                        user_id=b.owner_id,
                        business_id=b.id,
                        template="subscription_pending_payment",
                        payload={"plan": plan, "message": "Payment pending — we'll notify you when it's confirmed."},
                        correlation_id=correlation_id,
                    )
                    # Emit audit: payment pending
                    try:
                        await audit_client.emit_audit(
                            service="msme-engine",
                            event_type="payment_pending",
                            payload={"plan": plan, "payment_response": pr_result},
                            actor_id=b.owner_id,
                            entity_type="business",
                            entity_id=b.id,
                            metadata={"correlation_id": correlation_id},
                        )
                    except Exception:
                        logger.exception("audit_emit_failed_payment_pending")
        except Exception:
            # best-effort: do not fail the main flow if notification fails
            logger.exception("notify_in_app_failed")

        return 201, result.model_dump(mode="json")

    # Early guard: require Authorization header for payment-initiating subscribe_and_pay requests.
    plan = _normalize_plan(payload.plan)
    if plan == _PLAN_PAID and payload.amount_minor and payload.phone_number:
        if not request.headers.get("Authorization"):
            raise HTTPException(status_code=401, detail="authorization_required_for_payment")

    status, body = await idempotent_execute(db=db, scope=scope_for("POST", "/business/{id}/subscribe_and_pay"), key=x_idempotency_key, run=_run)
    response.status_code = int(status)
    return body


@app.put("/business/{id}/subscription_price")
async def set_business_subscription_price(
    id: str,
    payload: SubscriptionPriceUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Set the subscription price (minor units) and billing interval for a business."""
    b = (await db.execute(select(Business).where(Business.id == id))).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="business_not_found")
    try:
        b.subscription_price_minor = int(payload.amount_minor)
        # normalize interval
        interval = _normalize_billing_interval(payload.billing_interval)
        # Update latest subscription if present
        sub = (
            await db.execute(
                select(BusinessSubscription).where(BusinessSubscription.business_id == b.id).order_by(BusinessSubscription.created_at.desc())
            )
        ).scalars().first()
        if sub:
            sub.billing_interval = interval
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("set_subscription_price_failed")
        raise HTTPException(status_code=500, detail="update_failed")
    return {"status": "ok", "business_id": b.id, "amount_minor": b.subscription_price_minor, "billing_interval": interval}


@app.put("/admin/subscription_price_default", response_model=DefaultSubscriptionPriceOut)
async def set_default_subscription_price(
    payload: DefaultSubscriptionPriceUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Admin: set the default subscription price for a billing interval.

    If `apply_to_missing` is true, update businesses that have NULL subscription_price_minor.
    """
    interval = _normalize_billing_interval(payload.billing_interval)
    try:
        # Upsert into subscription_pricing
        await db.execute(text(
            "INSERT INTO msme_engine.subscription_pricing (billing_interval, amount_minor, currency, updated_at) VALUES (:interval, :amt, :cur, now())"
            " ON CONFLICT (billing_interval) DO UPDATE SET amount_minor = EXCLUDED.amount_minor, currency = EXCLUDED.currency, updated_at = now()"
        ), {"interval": interval, "amt": int(payload.amount_minor), "cur": payload.currency or "ZMW"})
        if payload.apply_to_missing:
            await db.execute(text("UPDATE msme_engine.businesses SET subscription_price_minor = :amt WHERE subscription_price_minor IS NULL"), {"amt": int(payload.amount_minor)})
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("set_default_subscription_price_failed")
        raise HTTPException(status_code=500, detail="update_failed")

    # Return the effective row
    row = (await db.execute(text("SELECT billing_interval, amount_minor, currency, updated_at FROM msme_engine.subscription_pricing WHERE billing_interval = :interval"), {"interval": interval})).mappings().first()
    if not row:
        raise HTTPException(status_code=500, detail="not_found_after_update")
    return DefaultSubscriptionPriceOut(billing_interval=row["billing_interval"], amount_minor=row["amount_minor"], currency=row["currency"], updated_at=row["updated_at"])


@app.get("/business/{id}/subscription", response_model=SubscriptionOut)
async def business_subscription(id: str, db: AsyncSession = Depends(get_db_session)):
    sub = (
        await db.execute(
            select(BusinessSubscription).where(BusinessSubscription.business_id == id).order_by(BusinessSubscription.created_at.desc())
        )
    ).scalars().first()
    if not sub:
        raise HTTPException(status_code=404, detail="subscription_not_found")
    return _subscription_out(sub)


@app.get("/business/{id}/entitlements", response_model=BusinessEntitlementsOut)
async def business_entitlements(id: str, db: AsyncSession = Depends(get_db_session)) -> BusinessEntitlementsOut:
    b = (await db.execute(select(Business).where(Business.id == id))).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="business_not_found")
    return _entitlements_for(b)


@app.get("/business/{id}/metadata", response_model=BusinessMetadataOut)
async def business_metadata(id: str, db: AsyncSession = Depends(get_db_session)):
    b = (await db.execute(select(Business).where(Business.id == id))).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="business_not_found")

    return BusinessMetadataOut(
        business_id=b.id,
        name=b.name,
        location=b.location,
        category=b.category,
        tags=b.tags,
        delivery_locations=b.delivery_locations,
        is_active=bool(b.is_active),
    )


@app.get("/business/phone/{phone_number}", response_model=BusinessPhoneLookupOut)
async def business_lookup_by_phone(phone_number: str, db: AsyncSession = Depends(get_db_session)):
    """Lookup business by owner phone number. Returns both user and business details.
    
    Uses optimized join query to fetch user and business in single database round-trip.
    """
    # Single query: Join User and Business on user.business_id = business.id
    stmt = (
        select(User, Business)
        .join(Business, User.business_id == Business.id)
        .where(User.phone == phone_number)
    )
    
    # Limit to a single row and return the first match to avoid MultipleResultsFound
    row = (await db.execute(stmt.limit(1))).first()
    if not row:
        raise HTTPException(status_code=404, detail="business_not_found_for_phone")

    user, b = row

    # Get user role
    _, role_name = await get_user_and_role(db, user.id)

    return BusinessPhoneLookupOut(
        business=_business_out(b),
        owner=UserOut(
            id=user.id,
            username=user.username,
            email=user.email,
            phone=user.phone,
            role=role_name,
            business_id=user.business_id,
            affiliate_id=user.affiliate_id,
            is_active=bool(user.is_active),
            signed_terms=bool(getattr(user, "signed_terms", False)),
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
    )


@app.post("/business/reindex")
async def business_reindex(request: Request, db: AsyncSession = Depends(get_db_session)):
    # Soft-launch: local no-op that returns how many MSMEs would be reindexed.
    count = (await db.execute(select(Business))).scalars().all()
    await _record_event(
        db=db,
        event_id=f"reindex:{uuid.uuid4().hex}",
        event_type="reindex_requested",
        business_id=None,
        source="business_service",
        correlation_id=getattr(request.state, "correlation_id", None),
        meta={"count": len(count)},
    )
    return {"status": "ok", "count": len(count)}


# ---- Payment events ----


@app.post("/events/payment_success")
async def payment_success(
    request: Request,
    payload: PaymentSuccessEvent,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    key = x_idempotency_key or payload.event_id

    async def _run():
        b = (await db.execute(select(Business).where(Business.id == payload.business_id))).scalar_one_or_none()
        if not b:
            raise HTTPException(status_code=404, detail="business_not_found")

        plan = _normalize_plan(payload.plan)

        # Activate latest subscription or create one.
        sub = (
            await db.execute(
                select(BusinessSubscription)
                .where(BusinessSubscription.business_id == b.id)
                .order_by(BusinessSubscription.created_at.desc())
            )
        ).scalars().first()

        if not sub:
            sub = BusinessSubscription(business_id=b.id, plan=plan, status="active")
            db.add(sub)
            await db.commit()
            await db.refresh(sub)

        sub.plan = plan
        sub.billing_interval = _normalize_billing_interval(payload.billing_interval or sub.billing_interval)
        sub.status = "active"
        # Ensure `sub.start_date` is a non-None datetime for downstream logic
        if sub.start_date is None:
            sub.start_date = datetime.now(timezone.utc)

        amount_minor = int(payload.amount * 100) if payload.amount is not None else None
        unit_price_minor = int(b.subscription_price_minor or 0)
        periods_paid = _compute_periods_paid(amount_minor=amount_minor, unit_price_minor=unit_price_minor)
        if periods_paid > 0:
            # Narrow `sub.start_date` to a non-None `datetime` for the type checker.
            if sub.start_date is None:
                start_dt: datetime = datetime.now(timezone.utc)
            else:
                start_dt: datetime = sub.start_date
            paid_through = _compute_paid_through(start_dt, periods_paid, sub.billing_interval)
            # store numeric value (convert Decimal to float) to match model column type
            sub.periods_paid = float(periods_paid)
            sub.paid_through = paid_through
            sub.end_date = paid_through
        else:
            sub.end_date = payload.paid_until
            sub.paid_through = payload.paid_until

        # If a paid subscription is expired/invalid, entitlements will downgrade automatically.
        b.subscription_plan = plan
        b.subscription_expiry = sub.end_date if plan == _PLAN_PAID else None

        await db.commit()

        await _record_event(
            db=db,
            event_id=payload.event_id,
            event_type="payment_success",
            business_id=b.id,
            source=payload.source or "payment_service",
            correlation_id=getattr(request.state, "correlation_id", None),
            meta=payload.model_dump(mode="json"),
        )

        # Attempt to correlate this payment success with a persisted PaymentInitiation
        try:
            # Prefer explicit correlation via `reference_id` present in the callback payload.
            ref_id = None
            try:
                raw_body = await request.json()
            except Exception:
                raw_body = {}

            if isinstance(raw_body, dict):
                ref_id = (
                    raw_body.get("reference_id")
                    or raw_body.get("referenceId")
                    or raw_body.get("payment_id")
                    or raw_body.get("paymentId")
                    or raw_body.get("deposit_id")
                    or raw_body.get("depositId")
                )

            initiation = None
            if ref_id:
                initiation = (
                    await db.execute(
                        select(PaymentInitiation).where(PaymentInitiation.deposit_id == str(ref_id))
                    )
                ).scalar_one_or_none()

            # Fallback: Look for recent pending initiation for this business (best-effort correlation)
            if not initiation:
                initiation = (
                    await db.execute(
                        select(PaymentInitiation)
                        .where(PaymentInitiation.business_id == b.id)
                        .where(PaymentInitiation.status == "pending")
                        .order_by(PaymentInitiation.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()

            affiliate_to_emit = None
            if initiation and initiation.affiliate_id:
                # Perform initiation.status update and Outbox insert atomically.
                try:
                    async with db.begin():
                        # Re-select the initiation row for update inside the transaction
                        locked = (
                            await db.execute(
                                select(PaymentInitiation).where(PaymentInitiation.id == initiation.id).with_for_update()
                            )
                        ).scalar_one_or_none()
                        if not locked:
                            raise RuntimeError("initiation_not_found_during_transaction")

                        # Update initiation status
                        locked.status = "completed"

                        # Build outbox payload and insert OutboxEvent within same transaction
                        out_payload = {
                            "business_id": b.id,
                            "subscription_plan": payload.plan,
                            "amount": payload.amount,
                            "currency": payload.currency,
                            "occurred_at": datetime.now(timezone.utc).isoformat(),
                            "correlation_id": getattr(request.state, "correlation_id", None),
                            "affiliate_id": initiation.affiliate_id,
                            "event_id": payload.event_id,
                        }
                        # Use shared outbox helper to insert outbox row (async-aware)
                        from src.app.helpers.outbox.outbox import create_outbox_row

                        await create_outbox_row(db, "msme.subscription.payment_succeeded", out_payload)
                    # commit happens on context exit
                    affiliate_to_emit = initiation.affiliate_id
                except Exception:
                    logger.exception("outbox_transaction_failed")

        except Exception:
            logger.exception("initiation_correlation_failed")

        await _notify_in_app(
            db=db,
            user_id=b.owner_id,
            business_id=b.id,
            template="subscription_payment_success",
            payload={
                "plan": plan,
                "paid_until": payload.paid_until.isoformat().replace("+00:00", "Z") if payload.paid_until else None,
                "message": "Congratulations — payment received and your subscription is active.",
            },
            correlation_id=getattr(request.state, "correlation_id", None),
        )

        return 200, {"status": "ok"}

    _, body = await idempotent_execute(db=db, scope=scope_for("POST", "/events/payment_success"), key=key, run=_run)
    return body


@app.get("/events/business/{business_id}", response_model=list[MsmeEventOut])
async def events_for_business(business_id: str, limit: int = 200, offset: int = 0, db: AsyncSession = Depends(get_db_session)):
    rows = (
        await db.execute(
            select(MsmeEvent)
            .where(MsmeEvent.business_id == business_id)
            .order_by(MsmeEvent.occurred_at.desc())
            .limit(min(limit, 500))
            .offset(max(offset, 0))
        )
    ).scalars().all()

    return [
        MsmeEventOut(
            event_id=r.event_id,
            business_id=r.business_id,
            event_type=r.event_type,
            occurred_at=r.occurred_at,
            source=r.source,
            correlation_id=r.correlation_id,
            meta=r.meta,
            created_at=r.created_at,
        )
        for r in rows
    ]


@app.get("/notification/user/{user_id}")
async def notification_list_for_user(user_id: str, request: Request):
    base = get_notification_base_url().rstrip("/")
    headers: dict[str, str] = {}
    cid = request.headers.get("X-Correlation-Id")
    if cid:
        headers["X-Correlation-Id"] = cid
    auth = request.headers.get("Authorization")
    if auth:
        headers["Authorization"] = auth

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{base}/notification/user/{user_id}", headers=headers)
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="notification_service_unreachable")

    try:
        return JSONResponse(status_code=r.status_code, content=r.json())
    except Exception:
        return JSONResponse(status_code=r.status_code, content={"detail": "invalid_notification_response"})


@app.get("/notification/{id}")
async def notification_get(id: str, request: Request):
    base = get_notification_base_url().rstrip("/")
    headers: dict[str, str] = {}
    cid = request.headers.get("X-Correlation-Id")
    if cid:
        headers["X-Correlation-Id"] = cid
    auth = request.headers.get("Authorization")
    if auth:
        headers["Authorization"] = auth

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{base}/notification/{id}", headers=headers)
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="notification_service_unreachable")

    try:
        return JSONResponse(status_code=r.status_code, content=r.json())
    except Exception:
        return JSONResponse(status_code=r.status_code, content={"detail": "invalid_notification_response"})


# ---- Delivery locations endpoints ----


@app.get("/businesses/{business_id}/delivery-locations")
async def get_business_delivery_locations(business_id: str, db: AsyncSession = Depends(get_db_session)):
    """Return the delivery locations mapping for a business.

    Response example: {"Lusaka": {"price_minor": 2500, "currency": "ZMW"}, ...}
    """
    b = (await db.execute(select(Business).where(Business.id == business_id))).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="business_not_found")
    return b.delivery_locations or {}


@app.put("/businesses/{business_id}/delivery-locations")
async def update_business_delivery_locations(
    business_id: str,
    payload: DeliveryLocationsUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Replace the business's delivery locations. Caller must be authenticated.

    The payload must be a mapping of town -> metadata, where metadata includes at least `price_minor`.
    """
    # authorization: only allow owner or staff to update (simple check)
    b = (await db.execute(select(Business).where(Business.id == business_id))).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="business_not_found")

    # Very small authorization: user must be the business owner or have role 'admin' or 'staff'
    # Resolve role name for the current_user (User object doesn't include `role` attribute)
    _, role_name = await get_user_and_role(db, current_user.id)
    if getattr(current_user, "business_id", None) != business_id and role_name not in {"admin", "staff"}:
        raise HTTPException(status_code=403, detail="not_authorized")

    # Basic validation: ensure each entry has price_minor as int
    for town, meta in payload.delivery_locations.items():
        if not isinstance(meta, dict):
            raise HTTPException(status_code=400, detail=f"invalid_meta_for_{town}")
        if "price_minor" not in meta:
            raise HTTPException(status_code=400, detail=f"missing_price_minor_for_{town}")
        try:
            int(meta["price_minor"])
        except Exception:
            raise HTTPException(status_code=400, detail=f"invalid_price_minor_for_{town}")

    b.delivery_locations = payload.delivery_locations
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return b.delivery_locations or {}


# ---- Simple onboarding orchestration endpoints (frontend-friendly) ----


@app.post("/msme/onboard")
async def msme_onboard(payload: MSMEOnboardRequest, db: AsyncSession = Depends(get_db_session)):
    """Create a user (msme) + business and record products as an event.

    This is a convenience orchestration used by the onboarding page in the
    frontend. It is intentionally lightweight for soft-launch: products are
    emitted as an `msme_onboarded` event for downstream processing.
    """
    # Create user
    base_username = (payload.profile.email.split("@")[0] if payload.profile.email else (payload.profile.fullName or "msme")).replace(" ", "_")[:80]
    username = base_username
    role_id = await _role_id_for(db, "msme")
    user = User(
        username=username,
        email=payload.profile.email,
        phone=payload.profile.phone,
        password_hash=hash_password(secrets.token_urlsafe(12)),
        role_id=role_id,
        is_active=True,
        signed_terms=bool(getattr(payload, "signed_terms", False)),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # If commit fails due to uniqueness (email or username), try to recover.
        await db.rollback()
        # If a user with the same email already exists, reuse that user instead
        # of creating a duplicate. This makes the onboarding endpoint idempotent
        # for repeated requests using the same email.
        if payload.profile.email:
            try:
                res = await db.execute(select(User).where(User.email == payload.profile.email))
                existing = res.scalar_one_or_none()
                if existing:
                    user = existing
                else:
                    # No existing by email – fall back to changing username and retry
                    user.username = f"{username}-{secrets.token_hex(3)}"
                    db.add(user)
                    await db.commit()
            except Exception:
                # As a last resort, attempt username suffix and commit
                try:
                    user.username = f"{username}-{secrets.token_hex(3)}"
                    db.add(user)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
        else:
            # No email to check against – try username suffix and retry
            user.username = f"{username}-{secrets.token_hex(3)}"
            db.add(user)
            await db.commit()

    await db.refresh(user)

    # Create business
    b = Business(
        name=payload.business.businessName,
        owner_id=user.id,
        location=payload.profile.location,
        category=payload.business.businessType,
        is_active=True,
    )
    db.add(b)
    await db.commit()
    await db.refresh(b)

    # Link user to business
    user.business_id = b.id
    db.add(user)
    await db.commit()

    # generate msme code
    code = await _generate_msme_code(db)
    db.add(MsmeCode(business_id=b.id, code=code))
    await db.commit()

    # Emit onboarding event containing products payload for downstream workers
    try:
        await _record_event(
            db=db,
            event_id=f"msme_onboarded:{b.id}:{uuid.uuid4().hex}",
            event_type="msme_onboarded",
            business_id=b.id,
            source="msme_onboard_endpoint",
            correlation_id=None,
            meta={"products": [p.model_dump() for p in payload.products], "profile": payload.profile.model_dump(), "business": payload.business.model_dump()},
        )
    except Exception:
        logger.exception("msme_onboard_event_emit_failed")

    return JSONResponse(status_code=201, content=jsonable_encoder({"business": _business_out(b), "user": _user_out(user, "msme"), "msme_code": code}))


@app.post("/affiliate/onboard")
async def affiliate_onboard(payload: AffiliateOnboardRequest, db: AsyncSession = Depends(get_db_session)):
    """Create a simple affiliate user and emit an affiliate_onboarded event.
    """
    base_username = (payload.profile.email.split("@")[0] if payload.profile.email else (payload.profile.fullName or "affiliate")).replace(" ", "_")[:80]
    username = base_username
    role_id = await _role_id_for(db, "affiliate")
    # If email already exists, return conflict to avoid duplicate users
    if payload.profile.email:
        res = await db.execute(select(User).where(User.email == payload.profile.email))
        existing = res.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="email_already_exists")
    user = User(
        username=username,
        email=payload.profile.email,
        phone=payload.profile.phone,
        password_hash=hash_password(secrets.token_urlsafe(12)),
        role_id=role_id,
        is_active=True,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        user.username = f"{username}-{secrets.token_hex(3)}"
        db.add(user)
        await db.commit()

    await db.refresh(user)

    # Create affiliate in external Affiliate Engine. If creation fails,
    # delete the newly-created user and return an error. On success, save
    # the affiliate id from the Affiliate Engine to `user.affiliate_id`.
    affiliate_base = os.getenv("AFFILIATE_ENGINE_BASE_URL", "http://127.0.0.1:8510").rstrip("/")
    create_url = f"{affiliate_base}/affiliates"

    # We call the affiliate engine with profile+preferences and expect JSON
    # response containing an `affiliate_id` on success.
    try:
        # Include internal secret header when configured so Affiliate Engine
        # accepts service-to-service creation without a JWT.
        internal_secret = os.getenv("AFFILIATE_INTERNAL_SECRET")
        headers: dict[str, str] = {}
        if internal_secret:
            headers["X-Internal-Secret"] = internal_secret

        # Build flattened payload expected by Affiliate Engine (name/phone at top-level)
        profile = payload.profile.model_dump() if hasattr(payload, "profile") else {}
        prefs = payload.preferences.model_dump() if hasattr(payload, "preferences") and payload.preferences is not None else None
        body: dict = {
            "name": profile.get("fullName") or profile.get("full_name") or profile.get("name"),
            "phone": profile.get("phone"),
        }
        if prefs is not None:
            body["preferences"] = prefs
        # include optional fields if present on the request
        if hasattr(payload, "signed_terms"):
            body["signed_terms"] = bool(getattr(payload, "signed_terms"))
        if hasattr(payload, "about") and getattr(payload, "about") is not None:
            body["about"] = getattr(payload, "about")

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(create_url, json=body, headers=headers)
        if resp.status_code not in (200, 201):
            # remove user since affiliate creation failed
            await db.refresh(user)
            await db.delete(user)
            await db.commit()
            raise HTTPException(status_code=502, detail="affiliate_engine_error")
        data = resp.json()
        affiliate_id = data.get("affiliate_id") or data.get("id")
        if not affiliate_id:
            await db.refresh(user)
            await db.delete(user)
            await db.commit()
            raise HTTPException(status_code=502, detail="affiliate_engine_no_id")

        try:
            user.affiliate_id = str(affiliate_id)
        except Exception:
            user.affiliate_id = affiliate_id
        db.add(user)
        await db.commit()

    except httpx.RequestError:
        await db.refresh(user)
        await db.delete(user)
        await db.commit()
        raise HTTPException(status_code=502, detail="affiliate_engine_unreachable")
    except Exception:
        logger.exception("affiliate_onboard_external_failure")
        # If we've already deleted the user above we may hit here; ensure clean state
        try:
            await db.refresh(user)
            await db.delete(user)
            await db.commit()
        except Exception:
            pass
        raise

    try:
        await _record_event(
            db=db,
            event_id=f"affiliate_onboarded:{user.id}:{uuid.uuid4().hex}",
            event_type="affiliate_onboarded",
            business_id=None,
            source="affiliate_onboard_endpoint",
            correlation_id=None,
            meta={"preferences": payload.preferences.model_dump(), "profile": payload.profile.model_dump(), "affiliate_id": affiliate_id},
        )
    except Exception:
        logger.exception("affiliate_onboard_event_emit_failed")

    return JSONResponse(status_code=201, content=jsonable_encoder({"user": _user_out(user, "affiliate"), "affiliate_id": affiliate_id}))
