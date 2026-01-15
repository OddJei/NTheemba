from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
import logging
import time
import uuid
import httpx
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.config import get_jwt_secret, get_notification_base_url, get_notification_timeout_seconds
from src.app.db import Base, engine, get_db_session
from src.app.idempotency import idempotent_execute, scope_for
from src.app import audit_client
from src.app.models import (
    AuthSession,
    Business,
    BusinessSubscription,
    MsmeCode,
    MsmeEvent,
    Role,
    User,
    VerificationToken,
)
from src.app.schemas import (
    AuthLogin,
    AuthRegister,
    BusinessMetadataOut,
    BusinessEntitlementsOut,
    BusinessOut,
    BusinessRegister,
    BusinessRegisterOut,
    BusinessUpdate,
    LogoutRequest,
    MsmeEventOut,
    PaymentFailedEvent,
    PaymentSuccessEvent,
    RefreshRequest,
    SubscribeRequest,
    SubscriptionInitiateOut,
    SubscriptionOut,
    TokenPair,
    UserLookupOut,
    UserOut,
    UserUpdate,
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

app = FastAPI(title="MSME Engine (Soft Launch)")

logger = logging.getLogger("msme_engine")

_SERVICE = "msme-engine"

# Forward important Python logs (WARNING+) to audit-service.
audit_client.install_audit_log_forwarding(service=_SERVICE)


_PLAN_FREE = "free"
_PLAN_PAID = "paid"


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
_REQ_COUNT = Counter("http_requests_total", "Total HTTP requests", ["service", "method", "route", "status"])
_REQ_LATENCY = Histogram("http_request_duration_seconds", "HTTP request duration", ["service", "method", "route"])


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

    async for db in get_db_session():
        await _ensure_default_roles(db)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
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
        affiliate_code=b.affiliate_code,
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
    evt = MsmeEvent(
        event_id=event_id,
        event_type=event_type,
        business_id=business_id,
        source=source,
        correlation_id=correlation_id,
        meta=meta,
    )
    db.add(evt)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()


# ---- Auth ----


@app.post("/auth/register", response_model=UserOut)
async def auth_register(
    payload: AuthRegister,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
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
    identifier = payload.identifier.strip()
    user = (
        await db.execute(
            select(User).where(or_(User.username == identifier, User.email == identifier, User.phone == identifier))
        )
    ).scalar_one_or_none()

    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")

    _, role_name = await get_user_and_role(db, user.id)

    refresh_token = issue_refresh_token(user=user, role_name=role_name)
    access_token = issue_access_token(user=user, role_name=role_name)

    # persist refresh token as a revocable session
    exp_ts = jwt_decode(refresh_token, secret=get_jwt_secret()).get("exp")
    expires_at = datetime.fromtimestamp(int(exp_ts), tz=timezone.utc)
    session = AuthSession(user_id=user.id, token=refresh_token, expires_at=expires_at)
    db.add(session)
    await db.commit()

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@app.post("/auth/refresh", response_model=TokenPair)
async def auth_refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db_session)):
    token_payload = jwt_decode(payload.refresh_token, secret=get_jwt_secret())
    if token_payload.get("typ") != "refresh":
        raise HTTPException(status_code=401, detail="invalid_token")

    session = (
        await db.execute(select(AuthSession).where(AuthSession.token == payload.refresh_token))
    ).scalar_one_or_none()
    if not session or session.revoked:
        raise HTTPException(status_code=401, detail="session_revoked")

    user, role_name = await get_user_and_role(db, token_payload.get("sub"))

    access_token = issue_access_token(user=user, role_name=role_name)
    refresh_token = issue_refresh_token(user=user, role_name=role_name)

    # rotate refresh token
    session.revoked = True
    exp_ts = jwt_decode(refresh_token, secret=get_jwt_secret()).get("exp")
    expires_at = datetime.fromtimestamp(int(exp_ts), tz=timezone.utc)
    db.add(AuthSession(user_id=user.id, token=refresh_token, expires_at=expires_at))
    await db.commit()

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@app.post("/auth/logout")
async def auth_logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db_session)):
    session = (
        await db.execute(select(AuthSession).where(AuthSession.token == payload.refresh_token))
    ).scalar_one_or_none()
    if not session:
        return {"status": "ok"}

    session.revoked = True
    await db.commit()
    return {"status": "ok"}


@app.get("/auth/me", response_model=UserOut)
async def auth_me(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    role_name = "default"
    token_payload = getattr(request.state, "token_payload", None)
    if isinstance(token_payload, dict) and token_payload.get("role"):
        role_name = str(token_payload.get("role"))
    else:
        _, role_name = await get_user_and_role(db, user.id)

    return _user_out(user, role_name)


@app.get("/auth/phone/{user_phone}", response_model=UserLookupOut)
async def auth_phone_lookup(user_phone: str, db: AsyncSession = Depends(get_db_session)):
    user = (await db.execute(select(User).where(User.phone == user_phone))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    _, role_name = await get_user_and_role(db, user.id)
    return UserLookupOut(
        user_id=user.id,
        role=role_name,
        business_id=user.business_id,
        affiliate_id=user.affiliate_id,
        is_active=bool(user.is_active),
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
            role_id = await _role_id_for(db, "msme")
            owner = User(
                username=payload.owner.username,
                email=str(payload.owner.email),
                phone=payload.owner.phone,
                password_hash=hash_password(payload.owner.password),
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

        business = Business(
            name=payload.name,
            owner_id=owner_id,
            location=payload.location,
            category=payload.category,
            logo_url=payload.logo_url,
            affiliate_code=payload.affiliate_code,
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
                "affiliate_code": payload.affiliate_code,
                "referred_by_msme_code": payload.referred_by_msme_code,
            },
        )

        await _notify_in_app(
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
                "affiliate_code": payload.affiliate_code,
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
        sub = BusinessSubscription(business_id=b.id, plan=plan, status=sub_status)
        db.add(sub)
        await db.commit()
        await db.refresh(sub)

        if plan == _PLAN_FREE:
            b.subscription_plan = _PLAN_FREE
            b.subscription_expiry = None
            await db.commit()

            await _notify_in_app(
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

        await _notify_in_app(
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


@app.get("/business/phone/{phone_number}", response_model=BusinessOut)
async def business_lookup_by_phone(phone_number: str, db: AsyncSession = Depends(get_db_session)):
    user = (await db.execute(select(User).where(User.phone == phone_number))).scalar_one_or_none()
    if not user or not user.business_id:
        raise HTTPException(status_code=404, detail="business_not_found")

    b = (await db.execute(select(Business).where(Business.id == user.business_id))).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="business_not_found")

    return _business_out(b)


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
        sub.status = "active"
        sub.start_date = sub.start_date or datetime.now(timezone.utc)
        sub.end_date = payload.paid_until

        # If a paid subscription is expired/invalid, entitlements will downgrade automatically.
        b.subscription_plan = plan
        b.subscription_expiry = payload.paid_until if plan == _PLAN_PAID else None

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

        await _notify_in_app(
            user_id=b.owner_id,
            business_id=b.id,
            template="subscription_payment_success",
            payload={"plan": plan, "paid_until": payload.paid_until.isoformat().replace("+00:00", "Z") if payload.paid_until else None},
            correlation_id=getattr(request.state, "correlation_id", None),
        )

        return 200, {"status": "ok"}

    _, body = await idempotent_execute(db=db, scope=scope_for("POST", "/events/payment_success"), key=key, run=_run)
    return body


@app.post("/events/payment_failed")
async def payment_failed(
    request: Request,
    payload: PaymentFailedEvent,
    db: AsyncSession = Depends(get_db_session),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    key = x_idempotency_key or payload.event_id

    async def _run():
        b = (await db.execute(select(Business).where(Business.id == payload.business_id))).scalar_one_or_none()
        if not b:
            raise HTTPException(status_code=404, detail="business_not_found")

        sub = (
            await db.execute(
                select(BusinessSubscription)
                .where(BusinessSubscription.business_id == b.id)
                .order_by(BusinessSubscription.created_at.desc())
            )
        ).scalars().first()
        if sub and sub.status == "pending_payment":
            sub.status = "expired"
            await db.commit()

        await _record_event(
            db=db,
            event_id=payload.event_id,
            event_type="payment_failed",
            business_id=b.id,
            source=payload.source or "payment_service",
            correlation_id=getattr(request.state, "correlation_id", None),
            meta=payload.model_dump(mode="json"),
        )

        await _notify_in_app(
            user_id=b.owner_id,
            business_id=b.id,
            template="subscription_payment_failed",
            payload={"reason": payload.reason, "plan": payload.plan},
            correlation_id=getattr(request.state, "correlation_id", None),
        )

        return 200, {"status": "ok"}

    _, body = await idempotent_execute(db=db, scope=scope_for("POST", "/events/payment_failed"), key=key, run=_run)
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
