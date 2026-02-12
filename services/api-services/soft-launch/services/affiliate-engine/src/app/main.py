from __future__ import annotations

import os
import secrets
import string
import uuid
import urllib.parse
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse, Response, JSONResponse
import logging
import time
import uuid
import asyncio
import json
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest, CollectorRegistry
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.config import (
    get_admin_key,
    get_affiliate_default_whatsapp_number,
    get_affiliate_token_prefix,
    get_affiliate_token_ttl_seconds,
    get_catalog_base_url,
    get_epoch_days_default,
    get_msme_base_url,
    get_notification_base_url,
    get_notification_timeout_seconds,
    get_payment_revenue_base_url,
    get_pool_pct_default,
    skip_link_target_validation,
    get_pg_schema,
)
from sqlalchemy import text
import httpx
from src.app.db import Base, engine, get_db_session
from src.app.idempotency import idempotent_execute, scope_for
from src.app.models import (
    Affiliate,
    AffiliateAttribution,
    AffiliateClick,
    AffiliateEarning,
    AffiliateEvent,
    AffiliateLink,
    AffiliateMetricSnapshot,
    AffiliateToken,
    AffiliateTier,
    AffiliateTierAssignment,
    AffiliateTierSetting,
    CommissionSettings,
    PoolAllocation,
    PoolEpoch,
    Outbox,
)
from src.app.pool import (
    close_epoch_and_allocate,
    compute_metrics_for_epoch,
    compute_payouts,
    compute_weighted_scores,
    compute_op_scores,
    ensure_default_tiers,
    ensure_default_tier_settings,
    get_or_create_settings,
    get_or_open_epoch,
    get_open_epoch,
    AffiliateMetrics,
    get_qualified_tiers,
)
from src.app.schemas import OrderDeliveredEvent
from src.app.schemas import (
    AffiliateCreate,
    AffiliateOut,
    AttributionCreate,
    AttributionOut,
    AffiliateLinkResolveOut,
    TokenResolveRequest,
    TokenResolveOut,
    ClickCreate,
    ClickOut,
    EarningOut,
    EarningsByDay,
    EarningsSummary,
    AffiliateDashboard,
    LinkCreate,
    LinkOut,
    PaymentSuccessEvent,
    CommissionSettingsOut,
    CommissionSettingsUpdate,
    EpochOut,
    EpochSetGrossRevenue,
    TierOut,
    TierAssign,
    TierThreshold,
    TierThresholdUpdate,
    PoolStanding,
    PoolStandingsOut,
    PoolAllocationOut,
    AffiliateEventOut,
    ProjectedPayoutOut,
    MetricSnapshotOut,
    MetricHistoryOut,
    PayoutStatusCallback,
    SessionCycleCreatedEvent,
)

from fastapi import Depends
from contextlib import asynccontextmanager

from src.app.events import OrderCreatedEvent
from src.app import audit_client
from src.app import security


@app.get("/outbox/pending")
async def outbox_pending_aff(request: Request):
    expected = (os.environ.get("OUTBOX_INTERNAL_SECRET") or "").strip()
    provided = (request.headers.get("X-Internal-Secret") or "").strip()
    if expected and (not provided or not secrets.compare_digest(expected, provided)):
        raise HTTPException(status_code=401, detail="invalid_internal_secret")

    now = datetime.now(timezone.utc)
    async with get_db_session() as db:
        q = select(Outbox).where(Outbox.status == "pending")
        # Only return items ready to be sent
        q = q.where((Outbox.send_after == None) | (Outbox.send_after <= now))
        res = await db.execute(q)
        rows = res.scalars().all()

    out = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "event_type": r.topic,
                "payload": r.payload,
                "dedupe_key": r.dedupe_key,
                "destination": r.destination,
                "attempts": r.attempts,
                "scheduled_at": (r.send_after.isoformat() if r.send_after else None),
                "correlation_id": None,
            }
        )

    return out


@app.post("/outbox/ack")
async def outbox_ack_aff(request: Request, body: dict):
    expected = (os.environ.get("OUTBOX_INTERNAL_SECRET") or "").strip()
    provided = (request.headers.get("X-Internal-Secret") or "").strip()
    if expected and (not provided or not secrets.compare_digest(expected, provided)):
        raise HTTPException(status_code=401, detail="invalid_internal_secret")

    ids = body.get("ids") or []
    if not ids:
        return {"acked": []}

    async with get_db_session() as db:
        res = await db.execute(select(Outbox).where(Outbox.id.in_(ids)))
        rows = res.scalars().all()
        acked = []
        for r in rows:
            r.status = "sent"
            r.updated_at = datetime.now(timezone.utc)
            acked.append(r.id)
        if acked:
            await db.commit()

    return {"acked": acked}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure per-service schema exists (Postgres) and set search_path so
    # `Base.metadata.create_all()` creates tables in the correct schema.
    async with engine.begin() as conn:
        try:
            schema = get_pg_schema()
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            await conn.execute(text(f"SET search_path TO {schema}"))
        except Exception:
            # Non-Postgres backends will ignore schema operations.
            pass

        await conn.run_sync(Base.metadata.create_all)

    # Ensure default pool config exists.
    await _ensure_schema_and_defaults()

    yield


app = FastAPI(title="Affiliate Engine (Soft Launch)", lifespan=lifespan)


async def _ensure_schema_and_defaults() -> None:
    async with get_db_session() as db:
        settings = await get_or_create_settings(
            db,
            pool_pct_default=get_pool_pct_default(),
            epoch_days_default=get_epoch_days_default(),
        )
        await ensure_default_tiers(db)
        await ensure_default_tier_settings(db)
        await get_or_open_epoch(db, pool_pct=float(settings.pool_pct), epoch_days=int(settings.epoch_days))


async def startup_event() -> None:
    # Ensure per-service schema exists (Postgres) and set search_path so
    # `Base.metadata.create_all()` creates tables in the correct schema.
    async with engine.begin() as conn:
        try:
            schema = get_pg_schema()
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            await conn.execute(text(f"SET search_path TO {schema}"))
        except Exception:
            # Non-Postgres backends will ignore schema operations.
            pass

        await conn.run_sync(Base.metadata.create_all)

    # Ensure default pool config exists.
    await _ensure_schema_and_defaults()


# Register startup handler for test compatibility without using the deprecated decorator.
app.add_event_handler("startup", startup_event)

logger = logging.getLogger("affiliate_engine")

_SERVICE = "affiliate-engine"
_PROM_REGISTRY = CollectorRegistry()

# Use a dedicated registry so tests can import the app multiple times without
# causing duplicate timeseries errors in the global CollectorRegistry.
try:
    _REQ_COUNT = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["service", "method", "route", "status"],
        registry=_PROM_REGISTRY,
    )
    _REQ_LATENCY = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration",
        ["service", "method", "route"],
        registry=_PROM_REGISTRY,
    )
except ValueError:
    # If metrics were already registered in this registry (re-imports/tests),
    # reuse the existing collectors to avoid ValueError on duplicated timeseries.
    _REQ_COUNT = _PROM_REGISTRY._names_to_collectors.get("http_requests_total")
    _REQ_LATENCY = _PROM_REGISTRY._names_to_collectors.get("http_request_duration_seconds")

# Forward important Python logs (WARNING+) to audit-service.
audit_client.install_audit_log_forwarding(service=_SERVICE)

_AUTH_SKIP_PATHS = {
    "/health",
    "/metrics",
    "/openapi.json",
    "/docs",
    "/docs/index.html",
    "/redoc",
    "/callbacks/payout-status",
}

# Prefix-based public routes (e.g. affiliate click landing/resolve endpoints).
_AUTH_SKIP_PREFIXES = (
    "/a/",
    "/affiliates",
    "/track",
    "/events",
    "/pool",
    "/admin",
    "/attribute",
)

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


async def _notify_channels(*, user_id: str | None, business_id: str | None, template: str, payload: dict | None, correlation_id: str | None, channels: list[str]) -> None:
    """Send notifications on multiple channels via the notification service.

    Channels are strings understood by the notification service, e.g. `in_app`, `sms`, `email`.
    """
    base = get_notification_base_url().rstrip("/")
    timeout = get_notification_timeout_seconds()
    headers: dict[str, str] = {}
    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            for ch in channels:
                await client.post(
                    f"{base}/notification/send",
                    json={
                        "channel": ch,
                        "user_id": user_id,
                        "business_id": business_id,
                        "template": template,
                        "payload": payload or {},
                    },
                    headers=headers,
                )
    except httpx.RequestError:
        logger.info("notification_unreachable_multi", extra={"template": template, "correlation_id": correlation_id, "channels": channels})


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


@app.post("/events/order/delivered")
async def ingest_order_delivered(request: Request, payload: OrderDeliveredEvent):
    """Mark affiliate sale events as delivered when order-delivery confirms delivery.

    This updates `AffiliateEvent.delivered_at` for any sale events matching the `order_id` and
    marks corresponding `AffiliateAttribution` as `delivered`.
    """
    updated = 0
    attr = None
    async with get_db_session() as db:
        # Update matching sale events
        res = await db.execute(
            select(AffiliateEvent).where(AffiliateEvent.order_id == payload.order_id, AffiliateEvent.event_type == "sale")
        )
        rows = res.scalars().all()
        for ev in rows:
            ev.delivered_at = payload.occurred_at
            updated += 1

        # Update attribution status if present
        res2 = await db.execute(select(AffiliateAttribution).where(AffiliateAttribution.order_id == payload.order_id))
        attr = res2.scalar_one_or_none()
        if attr:
            attr.status = "delivered"

        if updated or attr:
            await db.commit()

    # Emit audit event when attribution is marked as delivered
    if attr:
        audit_client.emit_audit_sync(
            service="affiliate-engine",
            event_type="affiliate_attribution_delivered",
            payload={
                "order_id": payload.order_id,
                "affiliate_id": attr.affiliate_id,
                "delivered_at": payload.occurred_at.isoformat(),
            },
            entity_type="affiliate_attribution",
            entity_id=attr.id,
            metadata={"correlation_id": getattr(request.state, "correlation_id", None)},
        )

    return {"updated_events": updated, "attribution_updated": bool(attr)}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Require Bearer access tokens issued by msme-engine for all routes except health/metrics/docs.
    if request.url.path in _AUTH_SKIP_PATHS or any(request.url.path.startswith(p) for p in _AUTH_SKIP_PREFIXES):
        return await call_next(request)
    try:
        await security.require_access_token(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


@app.get("/admin/epochs/{epoch_id}/debug-scores")
async def admin_debug_epoch_scores(epoch_id: str, db: AsyncSession = Depends(get_db_session)):
    """Return computed metrics, raw and final OP scores and debug details for an epoch.

    Useful for inspecting `compute_op_scores` behavior during tests.
    """
    res = await db.execute(select(PoolEpoch).where(PoolEpoch.id == epoch_id))
    epoch = res.scalar_one_or_none()
    if not epoch:
        raise HTTPException(status_code=404, detail="epoch_not_found")

    metrics = await compute_metrics_for_epoch(db, epoch)

    # Load settings (weights) if present
    settings_row = (await db.execute(select(CommissionSettings).where(CommissionSettings.id == 1))).scalar_one_or_none()
    weights = (settings_row.weights if settings_row else None)

    scores, details = await compute_op_scores(db, metrics, weights)

    # Serialize metrics dataclasses to plain dicts
    metrics_out = []
    for m in metrics:
        metrics_out.append(
            {
                "affiliate_id": m.affiliate_id,
                "sales_volume": m.sales_volume,
                "unique_buyers": m.unique_buyers,
                "msme_referrals": m.msme_referrals,
                "clicks": m.clicks,
                "attributions": m.attributions,
                "paid_attributions": m.paid_attributions,
                "session_cycles": m.session_cycles,
                "tier_name": m.tier_name,
                "tier_multiplier": m.tier_multiplier,
            }
        )

    return {
        "epoch_id": epoch.id,
        "starts_at": epoch.starts_at.isoformat(),
        "ends_at": (epoch.ends_at.isoformat() if epoch.ends_at else None),
        "metrics": metrics_out,
        "scores": scores,
        "details": details,
    }


# db_session is defined above token_resolve to make it available to Depends()


@app.post("/token/resolve", response_model=TokenResolveOut)
async def token_resolve(
    request: Request,
    payload: TokenResolveRequest,
) -> TokenResolveOut:
    # Auth enforced by middleware; decoded payload is on request.state.token_payload
    token_str = payload.token
    # Accept `ace:xxxx` or raw token
    prefix = get_affiliate_token_prefix()
    if token_str.startswith(prefix):
        token_val = token_str[len(prefix) :]
    else:
        token_val = token_str

    # Lookup token
    async with get_db_session() as db:
        res = await db.execute(select(AffiliateToken).where(AffiliateToken.token == token_val))
        token_row = res.scalar_one_or_none()
    if not token_row:
        raise HTTPException(status_code=404, detail="token_not_found")

    now = datetime.now(timezone.utc)
    # Normalize expires_at to timezone-aware for safe comparison (SQLite may return naive datetimes).
    if getattr(token_row.expires_at, "tzinfo", None) is None:
        token_row.expires_at = token_row.expires_at.replace(tzinfo=timezone.utc)

    if token_row.expires_at < now:
        raise HTTPException(status_code=410, detail="token_expired")

    if token_row.used:
        raise HTTPException(status_code=409, detail="token_already_used")

    # Verify caller business identity (from access token payload or header)
    token_payload = getattr(request.state, "token_payload", {}) or {}
    caller_business = token_payload.get("business_id") or request.headers.get("X-Business-Id")
    if not caller_business:
        raise HTTPException(status_code=401, detail="business_auth_required")

    if str(caller_business) != str(token_row.business_id):
        raise HTTPException(status_code=403, detail="token_business_mismatch")

    # Mark token used (single-use)
    token_row.used = True
    token_row.used_at = now

    # Capture optional buyer/session info supplied by the bot
    buyer_phone_raw = getattr(payload, "buyer_phone", None)
    session_id = getattr(payload, "session_id", None)
    buyer_phone = _sanitize_whatsapp_number(buyer_phone_raw)

    # Persist buyer/session to token meta for auditing/reference
    meta = token_row.meta or {}
    if buyer_phone is not None:
        meta["buyer_phone"] = buyer_phone
    if session_id is not None:
        meta["session_id"] = session_id
    token_row.meta = meta

    # Fetch product details from catalog
    product = None
    try:
        catalog_url = get_catalog_base_url()
        async with httpx.AsyncClient(timeout=3.5) as client:
            r = await client.get(f"{catalog_url}/catalog/product/{token_row.product_id}")
            if r.status_code == 200:
                product = r.json() if isinstance(r.json(), dict) else None
    except httpx.RequestError:
        product = None

    # Record an event and persist token state
    async with get_db_session() as db:
        db.add(token_row)
        await _record_event(
            db,
                AffiliateEvent(
                event_id=str(uuid.uuid4()),
                affiliate_id=token_row.affiliate_id,
                event_type="token_resolved",
                occurred_at=now,
                source="token_resolve",
                correlation_id=getattr(request.state, "correlation_id", None),
                buyer_phone=buyer_phone,
                session_id=session_id,
                order_id=None,
                business_id=token_row.business_id,
                amount_zmw=None,
                meta={"token": token_row.token, "first_token_link_id": token_row.link_id},
            ),
        )
        await db.commit()

    out = TokenResolveOut(
        product_id=token_row.product_id,
        name=(product.get("name") if isinstance(product, dict) else None),
        price=(product.get("price") if isinstance(product, dict) else None),
        currency=(product.get("currency") if isinstance(product, dict) else "ZMW"),
        product_url=(product.get("product_url") if isinstance(product, dict) else None),
        image_url=(product.get("image_url") if isinstance(product, dict) else None),
        affiliate_id=token_row.affiliate_id,
        campaign=None,
        meta=token_row.meta,
    )

    return out


def _sanitize_whatsapp_number(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip().replace(" ", "").replace("-", "")
    if s.startswith("+"):
        s = s[1:]
    if not s.isdigit():
        return None
    return s


def _extract_whatsapp_number(entitlements: dict | None) -> str | None:
    if not isinstance(entitlements, dict):
        return None
    # Try common keys that MSME / bot services may expose.
    for key in (
        "whatsapp_number",
        "whatsapp_phone",
        "chatbot_whatsapp_number",
        "chatbot_phone",
        "bot_phone",
        "business_phone",
        "phone",
    ):
        v = entitlements.get(key)
        cleaned = _sanitize_whatsapp_number(v)
        if cleaned:
            return cleaned
    return None


def _product_preview(prod: dict | None) -> dict | None:
    if not isinstance(prod, dict):
        return None
    name = prod.get("name") or prod.get("title") or prod.get("product_name")
    price = prod.get("price") or prod.get("price_zmw") or prod.get("amount")
    currency = prod.get("currency") or "ZMW"
    out = {
        "name": name,
        "price": price,
        "currency": currency,
    }
    # remove null-ish values
    return {k: v for k, v in out.items() if v is not None}


@app.get("/a/{affiliate_code}/resolve", response_model=AffiliateLinkResolveOut)
async def resolve_affiliate_link(
    request: Request,
    affiliate_code: str,
    session_id: str | None = None,
    user_phone: str | None = None,
    correlation_id: str | None = None,
) -> AffiliateLinkResolveOut:
    # 1) Find link.
    async with get_db_session() as db:
        res = await db.execute(select(AffiliateLink).where(AffiliateLink.code == affiliate_code))
        link = res.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="affiliate_link_not_found")

    if not link.product_id or not link.business_id:
        return AffiliateLinkResolveOut(
            status="unavailable",
            reason="link_missing_product_or_business",
            affiliate_code=affiliate_code,
            link_id=link.id,
            affiliate_id=link.affiliate_id,
            business_id=link.business_id,
            product_id=link.product_id,
            campaign=link.campaign,
        )

    # 2) Validate MSME + product if enabled.
    ent: dict | None = None
    prod: dict | None = None
    if not skip_link_target_validation():
        msme_url = get_msme_base_url()
        catalog_url = get_catalog_base_url()
        try:
            async with httpx.AsyncClient(timeout=3.5) as client:
                r = await client.get(f"{msme_url}/business/{link.business_id}/entitlements")
                if r.status_code == 404:
                    return AffiliateLinkResolveOut(
                        status="unavailable",
                        reason="business_not_found",
                        affiliate_code=affiliate_code,
                        link_id=link.id,
                        affiliate_id=link.affiliate_id,
                        business_id=link.business_id,
                        product_id=link.product_id,
                        campaign=link.campaign,
                    )
                if r.status_code != 200:
                    return AffiliateLinkResolveOut(
                        status="unavailable",
                        reason="msme_error",
                        affiliate_code=affiliate_code,
                        link_id=link.id,
                        affiliate_id=link.affiliate_id,
                        business_id=link.business_id,
                        product_id=link.product_id,
                        campaign=link.campaign,
                    )
                ent = r.json() if isinstance(r.json(), dict) else {}
                if not bool(ent.get("is_active", True)):
                    return AffiliateLinkResolveOut(
                        status="unavailable",
                        reason="business_inactive",
                        affiliate_code=affiliate_code,
                        link_id=link.id,
                        affiliate_id=link.affiliate_id,
                        business_id=link.business_id,
                        product_id=link.product_id,
                        campaign=link.campaign,
                    )
                if not bool(ent.get("affiliate_promo_links_enabled", False)):
                    return AffiliateLinkResolveOut(
                        status="unavailable",
                        reason="affiliate_links_not_allowed_for_plan",
                        affiliate_code=affiliate_code,
                        link_id=link.id,
                        affiliate_id=link.affiliate_id,
                        business_id=link.business_id,
                        product_id=link.product_id,
                        campaign=link.campaign,
                    )

                r = await client.get(f"{catalog_url}/catalog/product/{link.product_id}")
                if r.status_code != 200:
                    return AffiliateLinkResolveOut(
                        status="unavailable",
                        reason="product_not_found",
                        affiliate_code=affiliate_code,
                        link_id=link.id,
                        affiliate_id=link.affiliate_id,
                        business_id=link.business_id,
                        product_id=link.product_id,
                        campaign=link.campaign,
                    )
                prod = r.json() if isinstance(r.json(), dict) else {}
                prod_business = prod.get("business_id") if isinstance(prod, dict) else None
                if prod_business and str(prod_business) != str(link.business_id):
                    return AffiliateLinkResolveOut(
                        status="unavailable",
                        reason="product_business_mismatch",
                        affiliate_code=affiliate_code,
                        link_id=link.id,
                        affiliate_id=link.affiliate_id,
                        business_id=link.business_id,
                        product_id=link.product_id,
                        campaign=link.campaign,
                        product=_product_preview(prod),
                    )
        except httpx.RequestError:
            return AffiliateLinkResolveOut(
                status="unavailable",
                reason="upstream_unreachable",
                affiliate_code=affiliate_code,
                link_id=link.id,
                affiliate_id=link.affiliate_id,
                business_id=link.business_id,
                product_id=link.product_id,
                campaign=link.campaign,
            )

    # 3) Determine WhatsApp number.
    wa_number = _extract_whatsapp_number(ent) or _sanitize_whatsapp_number(get_affiliate_default_whatsapp_number())
    if not wa_number:
        return AffiliateLinkResolveOut(
            status="unavailable",
            reason="missing_whatsapp_number",
            affiliate_code=affiliate_code,
            link_id=link.id,
            affiliate_id=link.affiliate_id,
            business_id=link.business_id,
            product_id=link.product_id,
            campaign=link.campaign,
            product=_product_preview(prod),
        )

    # 4) Create a short-lived token.
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=get_affiliate_token_ttl_seconds())
    token = None
    for _ in range(3):
        candidate = _generate_code(length=24)
        token_row = AffiliateToken(
            token=candidate,
            link_id=link.id,
            affiliate_id=link.affiliate_id,
            product_id=link.product_id,
            business_id=link.business_id,
            expires_at=expires_at,
            meta={
                "correlation_id": correlation_id or getattr(request.state, "correlation_id", None),
                "session_id": session_id,
                "user_phone": user_phone,
                "user_agent": request.headers.get("user-agent"),
                "ip": request.client.host if request.client else None,
                "affiliate_code": affiliate_code,
            },
        )
        db.add(token_row)
        try:
            await db.commit()
            token = candidate
            break
        except IntegrityError:
            await db.rollback()
            continue

    if not token:
        return AffiliateLinkResolveOut(
            status="unavailable",
            reason="token_generation_failed",
            affiliate_code=affiliate_code,
            link_id=link.id,
            affiliate_id=link.affiliate_id,
            business_id=link.business_id,
            product_id=link.product_id,
            campaign=link.campaign,
            product=_product_preview(prod),
        )

    token_message = f"{get_affiliate_token_prefix()}{token}"
    # Machine-only marker to help bots detect token-containing messages
    marker = "[[AFFLINK]]"
    # Prefill includes token, a machine marker, then a short buyer-facing line
    prefill_text = f"{token_message} {marker} Hey 🖐\n i was directed here"
    whatsapp_url = f"https://wa.me/{wa_number}?text={urllib.parse.quote(prefill_text)}"

    # Optional: record a click + audit event for analytics.
    click = AffiliateClick(
        link_id=link.id,
        correlation_id=correlation_id or getattr(request.state, "correlation_id", None),
        session_id=session_id,
        user_phone=user_phone,
        meta={"source": "affiliate_link_resolve", "token": token},
    )
    async with get_db_session() as db:
        db.add(click)
        await _record_event(
            db,
            AffiliateEvent(
                event_id=str(uuid.uuid4()),
                affiliate_id=link.affiliate_id,
                event_type="campaign_click",
                occurred_at=click.occurred_at,
                source="affiliate_link_resolve",
                correlation_id=correlation_id or getattr(request.state, "correlation_id", None),
                buyer_phone=user_phone,
                session_id=session_id,
                order_id=None,
                business_id=link.business_id,
                amount_zmw=None,
                meta={"affiliate_code": affiliate_code, "link_id": link.id, "token": token},
            ),
        )
        await db.commit()

    return AffiliateLinkResolveOut(
        status="available",
        affiliate_code=affiliate_code,
        link_id=link.id,
        affiliate_id=link.affiliate_id,
        business_id=link.business_id,
        product_id=link.product_id,
        campaign=link.campaign,
        token=token,
        token_message=token_message,
        expires_at=expires_at,
        whatsapp_url=whatsapp_url,
        product=_product_preview(prod),
    )



@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(_PROM_REGISTRY), media_type=CONTENT_TYPE_LATEST)


def _require_admin(x_admin_key: Optional[str]) -> None:
    if not x_admin_key or x_admin_key != get_admin_key():
        raise HTTPException(status_code=401, detail="admin_unauthorized")


def _epoch_out(epoch: PoolEpoch) -> EpochOut:
    return EpochOut(
        id=epoch.id,
        starts_at=epoch.starts_at,
        ends_at=epoch.ends_at,
        status=epoch.status,
        gross_revenue_zmw=float(epoch.gross_revenue_zmw),
        pool_pct=float(epoch.pool_pct),
        pool_amount_zmw=float(epoch.pool_amount_zmw),
    )


def _settings_out(settings: CommissionSettings) -> CommissionSettingsOut:
    return CommissionSettingsOut(pool_pct=float(settings.pool_pct), epoch_days=int(settings.epoch_days), weights=settings.weights)


def _generate_code(length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _record_event(db: AsyncSession, event: AffiliateEvent) -> None:
    # Use a nested transaction so a duplicate event_id doesn't roll back the caller's work.
    try:
        async with db.begin_nested():
            db.add(event)
            await db.flush()
    except IntegrityError:
        return


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_db_session() as session:
        yield session


@app.post("/affiliates", response_model=AffiliateOut)
async def create_affiliate(
    request: Request,
    payload: AffiliateCreate,
    db: AsyncSession = Depends(db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
) -> AffiliateOut:
    async def _run():
        affiliate = Affiliate(name=payload.name, phone=payload.phone)
        db.add(affiliate)
        await db.commit()
        await db.refresh(affiliate)

        await _notify_in_app(
            user_id=str(affiliate.id),
            business_id=None,
            template="affiliate_created",
            payload={"name": affiliate.name},
            correlation_id=getattr(request.state, "correlation_id", None),
        )
        audit_client.emit_audit_sync(
            service="affiliate-engine",
            event_type="affiliate_created",
            payload={"affiliate_id": affiliate.id, "name": affiliate.name, "phone": affiliate.phone},
            entity_type="affiliate",
            entity_id=affiliate.id,
            metadata={"correlation_id": getattr(request.state, "correlation_id", None)},
        )
        return 200, AffiliateOut(**affiliate.__dict__)

    status_code, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", request.url.path),
        key=x_idempotency_key,
        run=_run,
    )
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail="unexpected_status")
    if isinstance(body, AffiliateOut):
        return body
    return AffiliateOut(**body)


@app.get("/affiliates/{affiliate_id}", response_model=AffiliateOut)
async def get_affiliate(affiliate_id: str, db: AsyncSession = Depends(db_session)) -> AffiliateOut:
    res = await db.execute(select(Affiliate).where(Affiliate.id == affiliate_id))
    affiliate = res.scalar_one_or_none()
    if not affiliate:
        raise HTTPException(status_code=404, detail="affiliate_not_found")
    return AffiliateOut(**affiliate.__dict__)


@app.get("/affiliates", response_model=list[AffiliateOut])
async def list_affiliates(limit: int = 50, offset: int = 0, db: AsyncSession = Depends(db_session)) -> list[AffiliateOut]:
    res = await db.execute(select(Affiliate).order_by(Affiliate.created_at.desc()).limit(limit).offset(offset))
    items = res.scalars().all()
    return [AffiliateOut(**a.__dict__) for a in items]


@app.post("/affiliates/{affiliate_id}/links", response_model=LinkOut)
async def create_link(
    request: Request,
    affiliate_id: str,
    payload: LinkCreate,
    db: AsyncSession = Depends(db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
) -> LinkOut:
    res = await db.execute(select(Affiliate).where(Affiliate.id == affiliate_id))
    affiliate = res.scalar_one_or_none()
    if not affiliate:
        raise HTTPException(status_code=404, detail="affiliate_not_found")

    async def _run():
        if not skip_link_target_validation():
            # Enforce that links reference an existing MSME and product.
            if not payload.product_id or not payload.business_id:
                raise HTTPException(status_code=400, detail="product_id_and_business_id_required")

            msme_url = get_msme_base_url()
            catalog_url = get_catalog_base_url()
            async with httpx.AsyncClient(timeout=3.0) as client:
                # Validate MSME exists and is entitled to affiliate promo link generation.
                try:
                    r = await client.get(f"{msme_url}/business/{payload.business_id}/entitlements")
                except httpx.RequestError:
                    raise HTTPException(status_code=502, detail="msme_unreachable")

                if r.status_code == 404:
                    raise HTTPException(status_code=404, detail="business_not_found")
                if r.status_code != 200:
                    raise HTTPException(status_code=502, detail="msme_error")

                ent = r.json() if isinstance(r.json(), dict) else {}
                if not bool(ent.get("is_active", True)):
                    raise HTTPException(status_code=403, detail="business_inactive")
                if not bool(ent.get("affiliate_promo_links_enabled", False)):
                    raise HTTPException(status_code=403, detail="affiliate_links_not_allowed_for_plan")

                r = await client.get(f"{catalog_url}/catalog/product/{payload.product_id}")
                if r.status_code != 200:
                    raise HTTPException(status_code=404, detail="product_not_found")
                prod = r.json()
                prod_business = prod.get("business_id") if isinstance(prod, dict) else None
                if prod_business and str(prod_business) != str(payload.business_id):
                    raise HTTPException(status_code=400, detail="product_business_mismatch")

        code = payload.code or _generate_code()
        link = AffiliateLink(
            affiliate_id=affiliate_id,
            code=code,
            campaign=payload.campaign,
            product_id=payload.product_id,
            business_id=payload.business_id,
        )
        db.add(link)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise HTTPException(status_code=409, detail="affiliate_code_conflict")

        await db.refresh(link)

        await _notify_in_app(
            user_id=str(affiliate.id),
            business_id=payload.business_id,
            template="affiliate_link_created",
            payload={"link_id": link.id, "code": link.code, "campaign": link.campaign, "product_id": link.product_id},
            correlation_id=getattr(request.state, "correlation_id", None),
        )
        audit_client.emit_audit_sync(
            service="affiliate-engine",
            event_type="link_created",
            payload={"link_id": link.id, "code": link.code, "campaign": link.campaign, "product_id": link.product_id},
            actor_id=affiliate_id,
            entity_type="link",
            entity_id=link.id,
            metadata={"correlation_id": getattr(request.state, "correlation_id", None)},
        )
        return 200, LinkOut(**link.__dict__)

    status_code, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", request.url.path),
        key=x_idempotency_key,
        run=_run,
    )
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail="unexpected_status")
    return LinkOut(**body)


@app.get("/affiliates/{affiliate_id}/links", response_model=list[LinkOut])
async def list_links(affiliate_id: str, db: AsyncSession = Depends(db_session)) -> list[LinkOut]:
    res = await db.execute(
        select(AffiliateLink).where(AffiliateLink.affiliate_id == affiliate_id).order_by(AffiliateLink.created_at.desc())
    )
    items = res.scalars().all()
    return [LinkOut(**l.__dict__) for l in items]


@app.post("/track/click", response_model=ClickOut)
async def track_click(
    request: Request,
    payload: ClickCreate,
    db: AsyncSession = Depends(db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
) -> ClickOut:
    async def _run():
        res = await db.execute(select(AffiliateLink).where(AffiliateLink.code == payload.affiliate_code))
        link = res.scalar_one_or_none()
        if not link:
            raise HTTPException(status_code=404, detail="affiliate_link_not_found")

        correlation_id = payload.correlation_id or getattr(request.state, "correlation_id", None)
        click = AffiliateClick(
            link_id=link.id,
            correlation_id=correlation_id,
            session_id=payload.session_id,
            user_phone=payload.user_phone,
            meta=payload.meta,
        )
        db.add(click)

        await _record_event(
            db,
            AffiliateEvent(
                event_id=payload.event_id,
                affiliate_id=link.affiliate_id,
                event_type="campaign_click",
                occurred_at=click.occurred_at,
                source="track_click",
                correlation_id=correlation_id,
                buyer_phone=payload.user_phone,
                session_id=payload.session_id,
                order_id=None,
                business_id=None,
                amount_zmw=None,
                meta={
                    "affiliate_code": payload.affiliate_code,
                    "link_id": link.id,
                    "meta": payload.meta,
                },
            ),
        )

        await db.commit()
        await db.refresh(click)
        audit_client.emit_audit_sync(
            service="affiliate-engine",
            event_type="click_tracked",
            payload={"click_id": click.id, "link_id": click.link_id, "user_phone": payload.user_phone},
            actor_id=payload.user_phone,
            entity_type="click",
            entity_id=click.id,
            metadata={"correlation_id": correlation_id},
        )
        return 200, ClickOut(id=click.id, link_id=click.link_id, occurred_at=click.occurred_at)

    status_code, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", request.url.path),
        key=x_idempotency_key or payload.event_id,
        run=_run,
    )
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail="unexpected_status")
    return ClickOut(**body)


@app.post("/attribute/order", response_model=AttributionOut)
async def attribute_order(
    request: Request,
    payload: AttributionCreate,
    db: AsyncSession = Depends(db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
) -> AttributionOut:
    async def _run():
        affiliate_id = payload.affiliate_id
        link_id = None

        if not affiliate_id and payload.affiliate_code:
            res = await db.execute(select(AffiliateLink).where(AffiliateLink.code == payload.affiliate_code))
            link = res.scalar_one_or_none()
            if not link:
                raise HTTPException(status_code=404, detail="affiliate_link_not_found")
            affiliate_id = link.affiliate_id
            link_id = link.id

        if not affiliate_id:
            raise HTTPException(status_code=400, detail="affiliate_id_or_code_required")

        click_id = payload.click_id

        # If click_id isn't provided, try infer latest click by session/user_phone (soft-launch convenience).
        if not click_id and (payload.session_id or payload.user_phone):
            click_q = (
                select(AffiliateClick)
                .join(AffiliateLink, AffiliateLink.id == AffiliateClick.link_id)
                .where(AffiliateLink.affiliate_id == affiliate_id)
                .order_by(AffiliateClick.occurred_at.desc())
                .limit(1)
            )
            if payload.session_id and payload.user_phone:
                click_q = click_q.where(
                    (AffiliateClick.session_id == payload.session_id) | (AffiliateClick.user_phone == payload.user_phone)
                )
            elif payload.session_id:
                click_q = click_q.where(AffiliateClick.session_id == payload.session_id)
            else:
                click_q = click_q.where(AffiliateClick.user_phone == payload.user_phone)

            inferred = (await db.execute(click_q)).scalar_one_or_none()
            if inferred:
                click_id = inferred.id
                if not link_id:
                    link_id = inferred.link_id

        # Idempotency by order_id unique constraint.
        attribution = AffiliateAttribution(
            affiliate_id=affiliate_id,
            link_id=link_id,
            order_id=payload.order_id,
            business_id=payload.business_id,
            click_id=click_id,
            session_id=payload.session_id,
            user_phone=payload.user_phone,
        )
        db.add(attribution)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            # return existing attribution if already present
            res = await db.execute(select(AffiliateAttribution).where(AffiliateAttribution.order_id == payload.order_id))
            existing = res.scalar_one_or_none()
            if existing:
                return 200, AttributionOut(
                    id=existing.id,
                    affiliate_id=existing.affiliate_id,
                    order_id=existing.order_id,
                    business_id=existing.business_id,
                    status=existing.status,
                    created_at=existing.created_at,
                )
            raise

        await db.refresh(attribution)

        await _record_event(
            db,
            AffiliateEvent(
                event_id=payload.event_id,
                affiliate_id=attribution.affiliate_id,
                event_type="conversion",
                occurred_at=attribution.created_at,
                source="attribute_order",
                correlation_id=payload.correlation_id or getattr(request.state, "correlation_id", None),
                buyer_phone=payload.user_phone,
                session_id=payload.session_id,
                order_id=payload.order_id,
                business_id=payload.business_id,
                amount_zmw=None,
                meta={
                    "affiliate_code": payload.affiliate_code,
                    "click_id": attribution.click_id,
                    "link_id": attribution.link_id,
                },
            ),
        )

        # Notify affiliate and admin about the conversion/attribution.
        try:
            await _notify_channels(
                user_id=attribution.affiliate_id,
                business_id=payload.business_id,
                template="affiliate_conversion",
                payload={"order_id": payload.order_id, "click_id": attribution.click_id},
                correlation_id=payload.correlation_id or getattr(request.state, "correlation_id", None),
                channels=["in_app", "sms"],
            )
            await _notify_channels(
                user_id=None,
                business_id=payload.business_id,
                template="affiliate_conversion_admin",
                payload={"order_id": payload.order_id, "affiliate_id": attribution.affiliate_id},
                correlation_id=payload.correlation_id or getattr(request.state, "correlation_id", None),
                channels=["in_app", "email"],
            )
        except Exception:
            logger.exception("notify_failed_on_attribution")

        return 200, AttributionOut(
            id=attribution.id,
            affiliate_id=attribution.affiliate_id,
            order_id=attribution.order_id,
            business_id=attribution.business_id,
            status=attribution.status,
            created_at=attribution.created_at,
        )

    status_code, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", request.url.path),
        key=x_idempotency_key or payload.event_id,
        run=_run,
    )
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail="unexpected_status")
    return AttributionOut(**body)


@app.get("/affiliates/{affiliate_id}/clicks", response_model=list[ClickOut])
async def list_clicks(
    affiliate_id: str, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(db_session)
) -> list[ClickOut]:
    res = await db.execute(
        select(AffiliateClick)
        .join(AffiliateLink, AffiliateLink.id == AffiliateClick.link_id)
        .where(AffiliateLink.affiliate_id == affiliate_id)
        .order_by(AffiliateClick.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = res.scalars().all()
    return [ClickOut(id=c.id, link_id=c.link_id, occurred_at=c.occurred_at) for c in items]


@app.get("/affiliates/{affiliate_id}/attributions", response_model=list[AttributionOut])
async def list_attributions(affiliate_id: str, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(db_session)) -> list[AttributionOut]:
    res = await db.execute(
        select(AffiliateAttribution)
        .where(AffiliateAttribution.affiliate_id == affiliate_id)
        .order_by(AffiliateAttribution.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = res.scalars().all()
    return [
        AttributionOut(
            id=a.id,
            affiliate_id=a.affiliate_id,
            order_id=a.order_id,
            business_id=a.business_id,
            status=a.status,
            created_at=a.created_at,
        )
        for a in items
    ]


@app.get("/events/affiliate/{affiliate_id}", response_model=list[AffiliateEventOut])
async def list_affiliate_events(
    affiliate_id: str, limit: int = 100, offset: int = 0, db: AsyncSession = Depends(db_session)
) -> list[AffiliateEventOut]:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit_out_of_range")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset_must_be_non_negative")

    res = await db.execute(
        select(AffiliateEvent)
        .where(AffiliateEvent.affiliate_id == affiliate_id)
        .order_by(AffiliateEvent.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = res.scalars().all()
    return [
        AffiliateEventOut(
            event_id=e.event_id,
            affiliate_id=e.affiliate_id,
            event_type=e.event_type,
            occurred_at=e.occurred_at,
            source=e.source,
            correlation_id=e.correlation_id,
            buyer_phone=e.buyer_phone,
            session_id=e.session_id,
            order_id=e.order_id,
            business_id=e.business_id,
            amount_zmw=float(e.amount_zmw) if e.amount_zmw is not None else None,
            meta=e.meta,
            created_at=e.created_at,
        )
        for e in items
    ]


@app.get("/notifications/stream")
async def notifications_stream(user_id: str | None = None, business_id: str | None = None):
    """Server-Sent Events endpoint streaming affiliate events in realtime.

    Optional filters: `user_id` (affiliate id) or `business_id`.
    """

    async def event_gen():
        last = datetime.now(timezone.utc) - timedelta(seconds=1)
        while True:
            async with get_db_session() as db:
                q = select(AffiliateEvent).where(AffiliateEvent.occurred_at > last)
                if user_id:
                    q = q.where(AffiliateEvent.affiliate_id == user_id)
                if business_id:
                    q = q.where(AffiliateEvent.business_id == business_id)
                q = q.order_by(AffiliateEvent.occurred_at.asc())
                rows = (await db.execute(q)).scalars().all()
                for e in rows:
                    last = e.occurred_at
                    payload = {
                        "event_id": e.event_id,
                        "affiliate_id": e.affiliate_id,
                        "event_type": e.event_type,
                        "occurred_at": e.occurred_at.isoformat(),
                        "buyer_phone": e.buyer_phone,
                        "session_id": e.session_id,
                        "order_id": e.order_id,
                        "business_id": e.business_id,
                        "meta": e.meta,
                    }
                    yield f"data: {json.dumps(payload, default=str)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.post("/events/payment-success")
async def ingest_payment_success(
    request: Request,
    payload: PaymentSuccessEvent,
    db: AsyncSession = Depends(db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
) -> dict:
    async def _run():
        order_id = payload.order_id
        if not order_id:
            raise HTTPException(status_code=400, detail="order_id_required")

        # Prefer explicit affiliate_id from payload earnings; else infer from attribution.
        affiliate_id = payload.earnings.affiliate_id
        affiliate_amount = payload.earnings.affiliate_amount

        if affiliate_amount is None:
            raise HTTPException(status_code=400, detail="earnings.affiliate_amount_required")

        if not affiliate_id:
            res = await db.execute(select(AffiliateAttribution).where(AffiliateAttribution.order_id == order_id))
            attr = res.scalar_one_or_none()
            if not attr:
                raise HTTPException(status_code=404, detail="attribution_not_found_for_order")
            affiliate_id = attr.affiliate_id
            # Do not mark attribution as paid here — payouts will come from the pool allocations only.
            attr.status = "attributed"

        await _record_event(
            db,
            AffiliateEvent(
                event_id=payload.event_id,
                affiliate_id=str(affiliate_id),
                event_type="sale",
                occurred_at=payload.occurred_at,
                source=payload.producer,
                correlation_id=payload.correlation_id,
                buyer_phone=payload.user_phone,
                session_id=None,
                order_id=order_id,
                business_id=payload.business_id,
                # Pool GMV metric: store the full sale amount (not commission) on the sale event.
                amount_zmw=float(payload.amount),
                meta={
                    "payment_id": payload.payment_id,
                    "amount": float(payload.amount),
                    "currency": payload.currency,
                    "earnings": payload.earnings.model_dump(mode="json"),
                    "affiliate_commission_zmw": float(affiliate_amount),
                },
            ),
        )

        # Notify affiliate and admin about the sale/achievement.
        try:
            # Notify affiliate: in-app + sms
            await _notify_channels(
                user_id=str(affiliate_id),
                business_id=payload.business_id,
                template="affiliate_sale",
                payload={"order_id": order_id, "amount": float(payload.amount), "currency": payload.currency},
                correlation_id=payload.correlation_id,
                channels=["in_app", "sms"],
            )
            # Notify admin/business: in-app + email (business admins are resolved by notification service)
            await _notify_channels(
                user_id=None,
                business_id=payload.business_id,
                template="affiliate_sale_admin",
                payload={"order_id": order_id, "affiliate_id": affiliate_id, "amount": float(payload.amount)},
                correlation_id=payload.correlation_id,
                channels=["in_app", "email"],
            )
        except Exception:
            logger.exception("notify_failed_on_payment_success")

        await db.commit()
        return 200, {"status": "ok", "affiliate_id": str(affiliate_id), "order_id": order_id}

    status_code, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", request.url.path),
        key=x_idempotency_key or payload.event_id,
        run=_run,
    )
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail="unexpected_status")
    return body


@app.post("/events/order-created")
async def ingest_order_created(
    request: Request,
    payload: OrderCreatedEvent,
    db: AsyncSession = Depends(db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
) -> dict:
    # If there's no affiliate_code or affiliate_id, nothing to do.
    if not payload.affiliate_code and not payload.affiliate_id:
        return {"status": "ignored", "reason": "no_affiliate_identifier"}

    attribution_payload = AttributionCreate(
        event_id=payload.event_id,
        affiliate_code=payload.affiliate_code,
        affiliate_id=payload.affiliate_id,
        order_id=payload.order_id,
        business_id=payload.business_id,
        correlation_id=payload.correlation_id,
        session_id=payload.session_id,
        user_phone=payload.user_phone,
    )

    async def _run():
        result = await attribute_order(
            request=request,
            payload=attribution_payload,
            db=db,
            x_idempotency_key=None,
        )
        # Emit audit event for order created and attribution
        audit_client.emit_audit_sync(
            service="affiliate-engine",
            event_type="affiliate_attribution_created",
            payload={
                "order_id": payload.order_id,
                "affiliate_id": payload.affiliate_id,
                "affiliate_code": payload.affiliate_code,
                "business_id": payload.business_id,
            },
            entity_type="affiliate_attribution",
            entity_id=result.id,
            metadata={"correlation_id": payload.correlation_id},
        )
        return 200, {"status": "ok", "attribution": result.model_dump()}

    status_code, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", request.url.path),
        key=x_idempotency_key or payload.event_id,
        run=_run,
    )
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail="unexpected_status")
    return body


@app.post("/events/session-cycle-created")
async def ingest_session_cycle_created(
    request: Request,
    payload: SessionCycleCreatedEvent,
    db: AsyncSession = Depends(db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
) -> dict:
    if not payload.affiliate_id:
        return {"status": "ignored", "reason": "no_affiliate_id"}

    async def _run():
        await _record_event(
            db,
            AffiliateEvent(
                event_id=payload.event_id,
                affiliate_id=str(payload.affiliate_id),
                event_type="session_cycle_created",
                occurred_at=payload.occurred_at,
                source=payload.producer,
                correlation_id=payload.correlation_id,
                buyer_phone=payload.user_phone,
                session_id=payload.session_id,
                order_id=None,
                business_id=payload.business_id,
                meta={
                    "cycle_id": payload.cycle_id,
                    "cycle_state": payload.cycle_state,
                    "meta": payload.meta,
                },
            ),
        )
        return 200, {"status": "ok"}

    status_code, body = await idempotent_execute(
        db=db,
        scope=scope_for("POST", request.url.path),
        key=x_idempotency_key or payload.event_id,
        run=_run,
    )
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail="unexpected_status")
    return body


@app.get("/affiliates/{affiliate_id}/earnings", response_model=EarningsSummary)
async def get_earnings(affiliate_id: str, db: AsyncSession = Depends(db_session)) -> EarningsSummary:
    total_q = select(func.coalesce(func.sum(AffiliateEarning.amount), 0.0)).where(
        AffiliateEarning.affiliate_id == affiliate_id
    )
    pending_q = select(func.coalesce(func.sum(AffiliateEarning.amount), 0.0)).where(
        AffiliateEarning.affiliate_id == affiliate_id,
        AffiliateEarning.status == "pending",
    )
    ready_q = select(func.coalesce(func.sum(AffiliateEarning.amount), 0.0)).where(
        AffiliateEarning.affiliate_id == affiliate_id,
        AffiliateEarning.status == "ready",
    )

    total = (await db.execute(total_q)).scalar_one()
    pending = (await db.execute(pending_q)).scalar_one()
    ready = (await db.execute(ready_q)).scalar_one()

    # Currency is per-row today; soft-launch: return ZMW by default.
    return EarningsSummary(
        affiliate_id=affiliate_id,
        currency="ZMW",
        total_amount=float(total),
        pending_amount=float(pending),
        ready_amount=float(ready),
    )


@app.get("/affiliates/{affiliate_id}/earnings/records", response_model=list[EarningOut])
async def list_earnings_records(
    affiliate_id: str, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(db_session)
) -> list[EarningOut]:
    res = await db.execute(
        select(AffiliateEarning)
        .where(AffiliateEarning.affiliate_id == affiliate_id)
        .order_by(AffiliateEarning.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = res.scalars().all()
    return [
        EarningOut(
            id=e.id,
            affiliate_id=e.affiliate_id,
            order_id=e.order_id,
            payment_id=e.payment_id,
            amount=float(e.amount),
            currency=e.currency,
            status=e.status,
            created_at=e.created_at,
        )
        for e in items
    ]


@app.get("/affiliates/{affiliate_id}/dashboard", response_model=AffiliateDashboard)
async def affiliate_dashboard(affiliate_id: str, days: int = 30, db: AsyncSession = Depends(db_session)) -> AffiliateDashboard:
    return await _build_affiliate_dashboard(db=db, affiliate_id=affiliate_id, days=days)


async def _build_affiliate_dashboard(db: AsyncSession, *, affiliate_id: str, days: int = 30) -> AffiliateDashboard:
    if days < 1:
        raise HTTPException(status_code=400, detail="days_must_be_positive")

    since = datetime.now(timezone.utc) - timedelta(days=days)

    clicks_q = (
        select(func.count(func.distinct(AffiliateClick.user_phone)))
        .select_from(AffiliateClick)
        .join(AffiliateLink, AffiliateLink.id == AffiliateClick.link_id)
        .where(
            AffiliateLink.affiliate_id == affiliate_id,
            AffiliateClick.occurred_at >= since,
            AffiliateClick.user_phone.is_not(None),
        )
    )
    attributions_q = select(func.count()).select_from(AffiliateAttribution).where(
        AffiliateAttribution.affiliate_id == affiliate_id,
        AffiliateAttribution.created_at >= since,
    )
    conversions_q = select(func.count()).select_from(AffiliateAttribution).where(
        AffiliateAttribution.affiliate_id == affiliate_id,
        AffiliateAttribution.created_at >= since,
        AffiliateAttribution.click_id.is_not(None),
    )

    last_click_q = (
        select(func.max(AffiliateClick.occurred_at))
        .select_from(AffiliateClick)
        .join(AffiliateLink, AffiliateLink.id == AffiliateClick.link_id)
        .where(AffiliateLink.affiliate_id == affiliate_id)
    )
    last_attr_q = select(func.max(AffiliateAttribution.created_at)).where(AffiliateAttribution.affiliate_id == affiliate_id)

    total_earnings_q = select(func.coalesce(func.sum(AffiliateEarning.amount), 0.0)).where(
        AffiliateEarning.affiliate_id == affiliate_id,
        AffiliateEarning.created_at >= since,
    )
    pending_earnings_q = select(func.coalesce(func.sum(AffiliateEarning.amount), 0.0)).where(
        AffiliateEarning.affiliate_id == affiliate_id,
        AffiliateEarning.created_at >= since,
        AffiliateEarning.status == "pending",
    )
    ready_earnings_q = select(func.coalesce(func.sum(AffiliateEarning.amount), 0.0)).where(
        AffiliateEarning.affiliate_id == affiliate_id,
        AffiliateEarning.created_at >= since,
        AffiliateEarning.status == "ready",
    )

    clicks = int((await db.execute(clicks_q)).scalar_one())
    attributions = int((await db.execute(attributions_q)).scalar_one())
    conversions = int((await db.execute(conversions_q)).scalar_one())

    last_click_at = (await db.execute(last_click_q)).scalar_one()
    last_attribution_at = (await db.execute(last_attr_q)).scalar_one()

    total_earnings = float((await db.execute(total_earnings_q)).scalar_one())
    pending_earnings = float((await db.execute(pending_earnings_q)).scalar_one())
    ready_earnings = float((await db.execute(ready_earnings_q)).scalar_one())

    conversion_rate = (conversions / clicks) if clicks else 0.0

    # SQLite-friendly day bucket.
    day_bucket = func.strftime("%Y-%m-%d", AffiliateEarning.created_at)
    series_q = (
        select(day_bucket.label("day"), func.coalesce(func.sum(AffiliateEarning.amount), 0.0).label("amount"))
        .where(AffiliateEarning.affiliate_id == affiliate_id, AffiliateEarning.created_at >= since)
        .group_by(day_bucket)
        .order_by(day_bucket.asc())
    )
    series_rows = (await db.execute(series_q)).all()
    earnings_by_day = [EarningsByDay(day=str(r.day), amount=float(r.amount)) for r in series_rows]

    return AffiliateDashboard(
        affiliate_id=affiliate_id,
        window_days=days,
        clicks=clicks,
        attributions=attributions,
        conversions=conversions,
        conversion_rate=float(conversion_rate),
        total_earnings=total_earnings,
        pending_earnings=pending_earnings,
        ready_earnings=ready_earnings,
        currency="ZMW",
        last_click_at=last_click_at,
        last_attribution_at=last_attribution_at,
        earnings_by_day=earnings_by_day,
    )


@app.get("/affiliates/{affiliate_id}/dashboard/stream")
async def affiliate_dashboard_stream(
    affiliate_id: str, days: int = 30
) -> StreamingResponse:
    # Simple Server-Sent Events (SSE) stream for realtime affiliate dashboards.
    async def event_gen():
        while True:
            async with get_db_session() as db:
                payload = await _build_affiliate_dashboard(db=db, affiliate_id=affiliate_id, days=days)
            yield f"data: {payload.model_dump_json()}\n\n"
            await asyncio.sleep(2)

    import asyncio

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/pool/standings", response_model=PoolStandingsOut)
async def pool_standings(db: AsyncSession = Depends(db_session)) -> PoolStandingsOut:
    settings = (await db.execute(select(CommissionSettings).where(CommissionSettings.id == 1))).scalar_one_or_none()
    if not settings:
        settings = await get_or_create_settings(
            db,
            pool_pct_default=get_pool_pct_default(),
            epoch_days_default=get_epoch_days_default(),
        )

    epoch = await get_or_open_epoch(db, pool_pct=float(settings.pool_pct), epoch_days=int(settings.epoch_days))
    metrics = await compute_metrics_for_epoch(db, epoch)
    scores, details = await compute_op_scores(db, metrics, settings.weights)

    pool_amount = float(epoch.gross_revenue_zmw) * float(settings.pool_pct)
    payouts = compute_payouts(scores, pool_amount)

    standings = [
        PoolStanding(
            affiliate_id=m.affiliate_id,
            tier_name=m.tier_name,
            tier_multiplier=float(m.tier_multiplier),
            effective_tier=details.get(m.affiliate_id, {}).get("effective_tier"),
            tier_qualification=details.get(m.affiliate_id, {}).get("tier_details"),
            sales_volume=float(m.sales_volume),
            unique_buyers=int(m.unique_buyers),
            msme_referrals=int(m.msme_referrals),
            clicks=int(m.clicks),
            attributions=int(m.attributions),
            paid_attributions=int(m.paid_attributions),
            session_cycles=int(m.session_cycles),
            op_raw=float(details.get(m.affiliate_id, {}).get("op_raw", 0.0)),
            op_final=float(details.get(m.affiliate_id, {}).get("op_final", 0.0)),
            eligible_for_multiplier=bool(details.get(m.affiliate_id, {}).get("eligible_for_multiplier", False)),
            effective_multiplier=float(details.get(m.affiliate_id, {}).get("effective_multiplier", 1.0)),
            weighted_score=float(scores.get(m.affiliate_id, 0.0)),
            projected_payout_zmw=float(payouts.get(m.affiliate_id, 0.0)),
        )
        for m in metrics
    ]
    standings.sort(key=lambda s: s.projected_payout_zmw, reverse=True)

    return PoolStandingsOut(
        epoch=_epoch_out(epoch),
        settings=_settings_out(settings),
        pool_amount_zmw=float(pool_amount),
        standings=standings,
    )


@app.get("/pool/standings/stream")
async def pool_standings_stream() -> StreamingResponse:
    # Simple Server-Sent Events (SSE) stream for realtime dashboards.
    async def event_gen():
        while True:
            async with get_db_session() as db:
                payload = await pool_standings(db)
            yield f"data: {payload.model_dump_json()}\n\n"
            await asyncio.sleep(2)

    import asyncio

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/affiliates/{affiliate_id}/projected-payout", response_model=ProjectedPayoutOut)
async def get_projected_payout(
    affiliate_id: str,
    db: AsyncSession = Depends(db_session),
    x_token: Optional[str] = Header(default=None, alias="X-Affiliate-Token"),
) -> ProjectedPayoutOut:
    """
    Calculate real-time projected payout for current epoch.
    
    Returns affiliate's current metrics, weighted score, tier qualification,
    and projected payout amount if the epoch ended today.
    """
    # 1. Verify affiliate exists
    affiliate = (await db.execute(select(Affiliate).where(Affiliate.id == affiliate_id))).scalar_one_or_none()
    if not affiliate:
        raise HTTPException(status_code=404, detail="affiliate_not_found")
    
    # 2. Get current open epoch
    epoch = await get_open_epoch(db)
    if not epoch:
        raise HTTPException(status_code=404, detail="no_open_epoch")
    
    # 3. Get settings
    settings = await get_or_create_settings(
        db,
        pool_pct_default=get_pool_pct_default(),
        epoch_days_default=get_epoch_days_default(),
    )
    
    # 4. Fetch affiliate metrics for current epoch
    metrics_list = await compute_metrics_for_epoch(db, epoch)
    affiliate_metrics = next(
        (m for m in metrics_list if m.affiliate_id == affiliate_id),
        None
    )
    
    if not affiliate_metrics:
        # Affiliate has no activity yet
        affiliate_metrics = AffiliateMetrics(
            affiliate_id=affiliate_id,
            sales_volume=0.0,
            unique_buyers=0,
            msme_referrals=0,
            clicks=0,
            attributions=0,
            paid_attributions=0,
            session_cycles=0,
            tier_name=None,
            tier_multiplier=1.0,
        )
    
    # 5. Get gross revenue
    gross_revenue = float(epoch.gross_revenue_zmw or 0.0)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{get_payment_revenue_base_url()}/epoch/{epoch.id}/gross-revenue",
                headers={"X-Admin-Key": get_admin_key()},
                timeout=5.0,
            )
            if response.status_code == 200:
                data = response.json()
                gross_revenue = float(data.get("gross_revenue_zmw", 0.0))
    except Exception as e:
        logger.debug(f"Failed to fetch gross revenue: {e}")

    # 6. Calculate projected payout using current epoch metrics
    pool_amount = gross_revenue * float(settings.pool_pct)
    if all(m.affiliate_id != affiliate_id for m in metrics_list):
        metrics_list.append(affiliate_metrics)

    scores, details = await compute_op_scores(db, metrics_list, settings.weights)
    payouts = compute_payouts(scores, pool_amount)

    weighted_score = float(scores.get(affiliate_id, 0.0))
    projected_payout = float(payouts.get(affiliate_id, 0.0))
    detail = details.get(affiliate_id, {})
    effective_tier = detail.get("effective_tier")
    tier_multiplier = float(detail.get("effective_multiplier", 1.0))
    qualified_tiers = await get_qualified_tiers(db, affiliate_metrics)

    # 7. Calculate affiliate share
    affiliate_share_pct = (projected_payout / pool_amount * 100) if pool_amount > 0 else 0.0
    epoch_ends_at = epoch.ends_at or (epoch.starts_at + timedelta(days=int(settings.epoch_days)))
    
    return ProjectedPayoutOut(
        affiliate_id=affiliate_id,
        epoch_id=epoch.id,
        epoch_ends_at=epoch_ends_at,
        # Metrics
        sales_volume=float(affiliate_metrics.sales_volume),
        unique_buyers=int(affiliate_metrics.unique_buyers),
        msme_referrals=int(affiliate_metrics.msme_referrals),
        clicks=int(affiliate_metrics.clicks),
        attributions=int(affiliate_metrics.attributions),
        paid_attributions=int(affiliate_metrics.paid_attributions),
        session_cycles=int(affiliate_metrics.session_cycles),
        # Scoring
        weighted_score=weighted_score,
        # Tier qualification
        qualified_tiers=qualified_tiers,
        effective_tier=effective_tier,
        tier_multiplier=float(tier_multiplier),
        # Payout calculation
        gross_revenue_zmw=gross_revenue,
        pool_pct=float(settings.pool_pct),
        pool_amount_zmw=pool_amount,
        affiliate_share_pct=affiliate_share_pct,
        projected_payout_zmw=projected_payout,
    )


@app.get("/affiliates/{affiliate_id}/metrics/history", response_model=MetricHistoryOut)
async def get_affiliate_metrics_history(
    affiliate_id: str,
    limit: int = 12,
    db: AsyncSession = Depends(db_session),
    x_token: Optional[str] = Header(default=None, alias="X-Affiliate-Token"),
):
    """
    Get historical metric snapshots for an affiliate across epochs.
    
    Returns:
    - List of metric snapshots ordered by epoch (newest first)
    - Each snapshot contains:
      - All 7 metrics (sales_volume, unique_buyers, msme_referrals, clicks, attributions, paid_attributions, session_cycles)
      - Weighted score, tier qualification, projected payout
    - Total snapshot count
    
    Args:
        affiliate_id: Affiliate ID
        limit: Maximum snapshots to return (default 12, i.e., 1 year of months)
    """
    # Verify affiliate exists
    affiliate = (await db.execute(select(Affiliate).where(Affiliate.id == affiliate_id))).scalar_one_or_none()
    if not affiliate:
        raise HTTPException(status_code=404, detail="affiliate_not_found")

    # Fetch metric snapshots ordered by epoch start time (newest first)
    query = (
        select(AffiliateMetricSnapshot)
        .where(AffiliateMetricSnapshot.affiliate_id == affiliate_id)
        .order_by(AffiliateMetricSnapshot.recorded_at.desc())
        .limit(limit)
    )
    snapshots = (await db.execute(query)).scalars().all()

    # Build response
    snapshot_outs = [MetricSnapshotOut.model_validate(s) for s in snapshots]
    
    date_range = None
    if snapshots:
        date_range = (snapshots[-1].recorded_at, snapshots[0].recorded_at)

    return MetricHistoryOut(
        affiliate_id=affiliate_id,
        snapshots=snapshot_outs,
        total_snapshots=len(snapshot_outs),
        date_range=date_range,
    )


@app.get("/affiliates/{affiliate_id}/metrics/snapshot/{epoch_id}", response_model=MetricSnapshotOut)
async def get_affiliate_metric_snapshot(
    affiliate_id: str,
    epoch_id: str,
    db: AsyncSession = Depends(db_session),
    x_token: Optional[str] = Header(default=None, alias="X-Affiliate-Token"),
):
    """
    Get metric snapshot for an affiliate at a specific epoch.
    
    Returns all 7 metrics, scoring, tier qualification, and payout projection for that epoch.
    
    Args:
        affiliate_id: Affiliate ID
        epoch_id: Epoch ID
    """
    snapshot = (
        await db.execute(
            select(AffiliateMetricSnapshot).where(
                (AffiliateMetricSnapshot.affiliate_id == affiliate_id)
                & (AffiliateMetricSnapshot.epoch_id == epoch_id)
            )
        )
    ).scalar_one_or_none()

    if not snapshot:
        raise HTTPException(status_code=404, detail="metric_snapshot_not_found")

    return MetricSnapshotOut.model_validate(snapshot)


@app.get("/admin/metrics/epoch/{epoch_id}", response_model=list[MetricSnapshotOut])
async def admin_get_epoch_metrics(
    epoch_id: str,
    db: AsyncSession = Depends(db_session),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """
    [ADMIN] Get all metric snapshots for an epoch (all affiliates).
    
    Returns:
    - Metric snapshots for all affiliates in the epoch
    - Ordered by weighted_score (highest first)
    
    Useful for:
    - Validating epoch calculations
    - Auditing affiliate scores
    - Understanding pool allocation
    """
    _require_admin(x_admin_key)

    query = (
        select(AffiliateMetricSnapshot)
        .where(AffiliateMetricSnapshot.epoch_id == epoch_id)
        .order_by(AffiliateMetricSnapshot.weighted_score.desc())
    )
    snapshots = (await db.execute(query)).scalars().all()

    return [MetricSnapshotOut.model_validate(s) for s in snapshots]


# ------------------- Callback Handlers -------------------


@app.post("/callbacks/payout-status")
async def handle_payout_status_callback(
    payload: PayoutStatusCallback,
    db: AsyncSession = Depends(db_session),
):
    """
    Receive payout status updates from payment-revenue service.
    
    Updates allocation status, records transactions, and emits audit events.
    
    Called when PawaPay completes or fails a payout batch.
    """
    allocation = (
        await db.execute(
            select(PoolAllocation).where(PoolAllocation.payout_id == payload.payout_id)
        )
    ).scalar_one_or_none()

    if not allocation:
        allocation = (
            await db.execute(
                select(PoolAllocation).where(
                    PoolAllocation.affiliate_id == payload.affiliate_id,
                    PoolAllocation.epoch_id == payload.epoch_id,
                )
            )
        ).scalar_one_or_none()

        if allocation:
            allocation.payout_id = payload.payout_id

    if not allocation:
        logger.warning(
            f"payout_callback_allocation_not_found payout_id={payload.payout_id} "
            f"affiliate_id={payload.affiliate_id} epoch_id={payload.epoch_id}"
        )
        return {"status": "ok"}  # Still return 200 to prevent retry loops

    # Update payout status
    allocation.payout_status = payload.status  # completed, failed
    allocation.payout_completed_at = payload.completed_at

    if payload.status == "failed":
        allocation.payout_error = payload.error_message
        logger.error(
            f"affiliate_payout_failed affiliate_id={allocation.affiliate_id} "
            f"payout_id={payload.payout_id} error={payload.error_message}"
        )
    else:
        logger.info(
            f"affiliate_payout_completed affiliate_id={allocation.affiliate_id} "
            f"amount_zmw={payload.amount_zmw}"
        )

    await db.commit()

    # Emit audit event
    await audit_client.emit_audit(
        service="affiliate-engine",
        event_type="affiliate_payout_completed",
        entity_type="pool_allocation",
        entity_id=allocation.id,
        payload={
            "payout_id": payload.payout_id,
            "affiliate_id": allocation.affiliate_id,
            "epoch_id": allocation.epoch_id,
            "amount_zmw": payload.amount_zmw,
            "status": payload.status,
            "error": payload.error_message,
        },
    )

    return {"status": "ok"}


# ------------------- Admin endpoints -------------------


@app.get("/admin/commission-settings", response_model=CommissionSettingsOut)
async def admin_get_settings(
    db: AsyncSession = Depends(db_session), x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key")
) -> CommissionSettingsOut:
    _require_admin(x_admin_key)
    settings = await get_or_create_settings(
        db,
        pool_pct_default=get_pool_pct_default(),
        epoch_days_default=get_epoch_days_default(),
    )
    return _settings_out(settings)


@app.put("/admin/commission-settings", response_model=CommissionSettingsOut)
async def admin_update_settings(
    payload: CommissionSettingsUpdate,
    db: AsyncSession = Depends(db_session),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> CommissionSettingsOut:
    _require_admin(x_admin_key)
    settings = await get_or_create_settings(
        db,
        pool_pct_default=get_pool_pct_default(),
        epoch_days_default=get_epoch_days_default(),
    )

    if payload.pool_pct is not None:
        settings.pool_pct = float(payload.pool_pct)
    if payload.epoch_days is not None:
        settings.epoch_days = int(payload.epoch_days)
    if payload.weights is not None:
        settings.weights = payload.weights

    await db.commit()
    return _settings_out(settings)


@app.get("/admin/tiers", response_model=list[TierOut])
async def admin_list_tiers(
    db: AsyncSession = Depends(db_session), x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key")
) -> list[TierOut]:
    _require_admin(x_admin_key)
    tiers = (await db.execute(select(AffiliateTier).order_by(AffiliateTier.name.asc()))).scalars().all()
    return [TierOut(name=t.name, multiplier=float(t.multiplier), price_zmw=float(t.price_zmw), active=bool(t.active)) for t in tiers]


@app.put("/admin/affiliates/{affiliate_id}/tier")
async def admin_assign_tier(
    affiliate_id: str,
    payload: TierAssign,
    db: AsyncSession = Depends(db_session),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> dict:
    _require_admin(x_admin_key)
    tier = (await db.execute(select(AffiliateTier).where(AffiliateTier.name == payload.tier_name))).scalar_one_or_none()
    if not tier:
        raise HTTPException(status_code=404, detail="tier_not_found")

    assignment = AffiliateTierAssignment(affiliate_id=affiliate_id, tier_name=payload.tier_name, ends_at=payload.ends_at)
    db.add(assignment)
    await db.commit()
    return {"status": "ok", "affiliate_id": affiliate_id, "tier": payload.tier_name}


@app.get("/admin/epochs", response_model=list[EpochOut])
async def admin_list_epochs(
    db: AsyncSession = Depends(db_session), x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key")
) -> list[EpochOut]:
    _require_admin(x_admin_key)
    epochs = (await db.execute(select(PoolEpoch).order_by(PoolEpoch.starts_at.desc()))).scalars().all()
    return [_epoch_out(e) for e in epochs]


@app.post("/admin/epochs/open", response_model=EpochOut)
async def admin_open_epoch(
    db: AsyncSession = Depends(db_session), x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key")
) -> EpochOut:
    _require_admin(x_admin_key)
    settings = await get_or_create_settings(
        db,
        pool_pct_default=get_pool_pct_default(),
        epoch_days_default=get_epoch_days_default(),
    )
    epoch = await get_or_open_epoch(db, pool_pct=float(settings.pool_pct), epoch_days=int(settings.epoch_days))
    return _epoch_out(epoch)


@app.put("/admin/epochs/{epoch_id}/gross-revenue", response_model=EpochOut)
async def admin_set_epoch_gross_revenue(
    epoch_id: str,
    payload: EpochSetGrossRevenue,
    db: AsyncSession = Depends(db_session),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> EpochOut:
    _require_admin(x_admin_key)
    epoch = (await db.execute(select(PoolEpoch).where(PoolEpoch.id == epoch_id))).scalar_one_or_none()
    if not epoch:
        raise HTTPException(status_code=404, detail="epoch_not_found")
    epoch.gross_revenue_zmw = float(payload.gross_revenue_zmw)
    await db.commit()
    return _epoch_out(epoch)


@app.post("/admin/epochs/{epoch_id}/close", response_model=list[PoolAllocationOut])
async def admin_close_epoch(
    epoch_id: str,
    db: AsyncSession = Depends(db_session),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> list[PoolAllocationOut]:
    _require_admin(x_admin_key)
    epoch = (await db.execute(select(PoolEpoch).where(PoolEpoch.id == epoch_id))).scalar_one_or_none()
    if not epoch:
        raise HTTPException(status_code=404, detail="epoch_not_found")
    if epoch.status != "open":
        raise HTTPException(status_code=409, detail="epoch_not_open")

    settings = await get_or_create_settings(
        db,
        pool_pct_default=get_pool_pct_default(),
        epoch_days_default=get_epoch_days_default(),
    )
    allocations = await close_epoch_and_allocate(db, epoch, settings)
    return [
        PoolAllocationOut(
            epoch_id=a.epoch_id,
            affiliate_id=a.affiliate_id,
            tier_name=a.tier_name,
            tier_multiplier=float(a.tier_multiplier),
            metrics=a.metrics,
            weighted_score=float(a.weighted_score),
            payout_zmw=float(a.payout_zmw),
            created_at=a.created_at,
        )
        for a in allocations
    ]


@app.get("/admin/epochs/{epoch_id}/allocations", response_model=list[PoolAllocationOut])
async def admin_list_allocations(
    epoch_id: str,
    db: AsyncSession = Depends(db_session),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> list[PoolAllocationOut]:
    _require_admin(x_admin_key)
    rows = (
        await db.execute(select(PoolAllocation).where(PoolAllocation.epoch_id == epoch_id).order_by(PoolAllocation.payout_zmw.desc()))
    ).scalars().all()
    return [
        PoolAllocationOut(
            epoch_id=a.epoch_id,
            affiliate_id=a.affiliate_id,
            tier_name=a.tier_name,
            tier_multiplier=float(a.tier_multiplier),
            metrics=a.metrics,
            weighted_score=float(a.weighted_score),
            payout_zmw=float(a.payout_zmw),
            created_at=a.created_at,
        )
        for a in rows
    ]


@app.get("/admin/tier-settings", response_model=list[TierThreshold])
async def get_tier_settings(
    db: AsyncSession = Depends(db_session),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> list[TierThreshold]:
    """Get all affiliate tier threshold settings.
    
    Returns the current tier thresholds configured for affiliate qualification.
    Can be adjusted by admins to change qualification criteria at runtime without code deployment.
    """
    _require_admin(x_admin_key)
    rows = (await db.execute(select(AffiliateTierSetting).order_by(AffiliateTierSetting.tier_name))).scalars().all()
    return [
        TierThreshold(
            tier_name=r.tier_name,
            gmv_min=float(r.gmv_min),
            buyers_min=int(r.buyers_min),
            referrals_min=int(r.referrals_min),
            session_cycles_min=int(r.session_cycles_min),
            min_metrics_required=int(r.min_metrics_required),
        )
        for r in rows
    ]


@app.put("/admin/tier-settings/{tier_name}", response_model=TierThreshold)
async def update_tier_setting(
    tier_name: str,
    update: TierThresholdUpdate,
    db: AsyncSession = Depends(db_session),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> TierThreshold:
    """Update threshold settings for a specific affiliate tier.
    
    Allows runtime adjustment of tier qualification criteria without code deployment.
    Only provided fields will be updated; omitted fields retain their current values.
    """
    _require_admin(x_admin_key)
    tier_name_normalized = tier_name.strip().lower()
    
    # Fetch existing setting
    result = await db.execute(
        select(AffiliateTierSetting).where(
            func.lower(AffiliateTierSetting.tier_name) == tier_name_normalized
        )
    )
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"tier_not_found: {tier_name}")
    
    # Update only provided fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(setting, field, value)
    
    await db.commit()
    await db.refresh(setting)
    
    return TierThreshold(
        tier_name=setting.tier_name,
        gmv_min=float(setting.gmv_min),
        buyers_min=int(setting.buyers_min),
        referrals_min=int(setting.referrals_min),
        session_cycles_min=int(setting.session_cycles_min),
        min_metrics_required=int(setting.min_metrics_required),
    )
