from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select


def _uuid() -> str:
    return str(uuid.uuid4())


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@pytest.mark.anyio
async def test_token_resolve_single_use(monkeypatch) -> None:
    monkeypatch.setenv("AFFILIATE_SKIP_LINK_TARGET_VALIDATION", "1")
    monkeypatch.setenv("AFFILIATE_DEFAULT_WHATSAPP_NUMBER", "+260970000000")

    from src.app.db import get_db_session
    from src.app.main import app
    from src.app.models import Affiliate, AffiliateLink, AffiliateToken
    from src.app.config import get_jwt_secret

    await app.router.startup()
    try:
        affiliate_id = _uuid()
        link_code = "code-resolve-2"
        product_id = _uuid()
        business_id = _uuid()

        async with get_db_session() as db:
            db.add(Affiliate(id=affiliate_id, name="A", phone="+260900000002"))
            db.add(
                AffiliateLink(
                    affiliate_id=affiliate_id,
                    code=link_code,
                    campaign="camp",
                    product_id=product_id,
                    business_id=business_id,
                )
            )
            await db.commit()

        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Create second-token via public resolve
            r = await ac.get(f"/a/{link_code}/resolve")
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "available"
            token_msg = body["token_message"]
            token_val = body["token"]

            # Build a valid JWT for the business (signed with service secret)
            header = {"alg": "HS256", "typ": "JWT"}
            payload = {"typ": "access", "business_id": business_id}
            h_secret = get_jwt_secret()
            header_b64 = _b64url_encode(json.dumps(header).encode("utf-8"))
            payload_b64 = _b64url_encode(json.dumps(payload).encode("utf-8"))
            signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
            sig = hmac.new(h_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
            sig_b64 = _b64url_encode(sig)
            jwt = f"{header_b64}.{payload_b64}.{sig_b64}"

            # Resolve token as bot
            auth_headers = {"Authorization": f"Bearer {jwt}"}
            resp = await ac.post("/token/resolve", json={"token": token_msg}, headers=auth_headers)
            assert resp.status_code == 200
            out = resp.json()
            assert out["product_id"] == product_id

            # Token should be marked used in DB
            async with get_db_session() as db:
                token_row = (await db.execute(select(AffiliateToken).where(AffiliateToken.token == token_val))).scalar_one_or_none()
                assert token_row is not None
                assert token_row.used is True

            # Second attempt should fail as already used
            resp2 = await ac.post("/token/resolve", json={"token": token_msg}, headers=auth_headers)
            assert resp2.status_code in (403, 409, 410)
    finally:
        await app.router.shutdown()
