from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.config import (
    get_access_token_minutes,
    get_jwt_secret,
    get_password_hash_iterations,
    get_refresh_token_days,
)
from src.app.db import get_db_session
from src.app.models import Role, User

_http_bearer = HTTPBearer(auto_error=False)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("ascii"))


def jwt_encode(payload: Dict[str, Any], *, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def jwt_decode(token: str, *, secret: str) -> Dict[str, Any]:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid_token")

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_sig, _b64url_decode(sig_b64)):
        raise HTTPException(status_code=401, detail="invalid_token")

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    exp = payload.get("exp")
    if exp is not None:
        now = int(dt.datetime.now(dt.timezone.utc).timestamp())
        if int(exp) < now:
            raise HTTPException(status_code=401, detail="token_expired")

    return payload


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password_required")

    iterations = get_password_hash_iterations()
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256$%d$%s$%s" % (iterations, _b64url_encode(salt), _b64url_encode(digest))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iters_s, salt_b64, digest_b64 = password_hash.split("$")
    except ValueError:
        return False

    if scheme != "pbkdf2_sha256":
        return False

    try:
        iterations = int(iters_s)
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(digest_b64)
    except Exception:
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def issue_access_token(*, user: User, role_name: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(minutes=get_access_token_minutes())
    payload = {
        "sub": user.id,
        "role": role_name,
        "business_id": user.business_id,
        "affiliate_id": user.affiliate_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "typ": "access",
    }
    return jwt_encode(payload, secret=get_jwt_secret())


def issue_refresh_token(*, user: User, role_name: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(days=get_refresh_token_days())
    payload = {
        "sub": user.id,
        "role": role_name,
        "business_id": user.business_id,
        "affiliate_id": user.affiliate_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "typ": "refresh",
        "jti": _b64url_encode(os.urandom(12)),
    }
    return jwt_encode(payload, secret=get_jwt_secret())


async def get_user_and_role(db: AsyncSession, user_id: str) -> tuple[User, str]:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="user_inactive")

    role_name = (
        await db.execute(select(Role.name).where(Role.id == user.role_id))
    ).scalar_one_or_none() or "default"
    return user, role_name


async def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_http_bearer),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="missing_token")

    payload = jwt_decode(creds.credentials, secret=get_jwt_secret())
    if payload.get("typ") != "access":
        raise HTTPException(status_code=401, detail="invalid_token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid_token")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="user_inactive")

    request.state.token_payload = payload
    return user
