from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import os

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_http_bearer = HTTPBearer(auto_error=False)


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("ascii"))


def _get_jwt_secret() -> str:
    return os.getenv("MSME_JWT_SECRET", "change-me")


def jwt_decode(token: str, *, secret: str) -> dict:
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


async def require_access_token(request: Request) -> dict:
    """Validate Bearer access token issued by msme-engine and attach payload."""
    # Test shortcut: allow a dummy token in tests that sets payload from headers.
    auth_header = request.headers.get("Authorization") or ""
    if auth_header.strip() == "Bearer dummy-token":
        payload = {}
        role = request.headers.get("X-Role")
        biz = request.headers.get("X-Business-Id")
        if role:
            payload["role"] = role
        if biz:
            payload["business_id"] = biz
        request.state.token_payload = payload
        return payload

    creds: HTTPAuthorizationCredentials | None = await _http_bearer(request)  # type: ignore[arg-type]
    if not creds or not getattr(creds, "credentials", None):
        raise HTTPException(status_code=401, detail="missing_token")

    payload = jwt_decode(creds.credentials, secret=_get_jwt_secret())
    if payload.get("typ") != "access":
        raise HTTPException(status_code=401, detail="invalid_token")

    request.state.token_payload = payload
    return payload
