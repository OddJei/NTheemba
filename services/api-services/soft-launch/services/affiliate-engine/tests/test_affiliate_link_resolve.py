from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select


def _uuid() -> str:
    return str(uuid.uuid4())


@pytest.mark.anyio
async def test_affiliate_link_resolve_returns_whatsapp_url(monkeypatch) -> None:
    # Ensure the resolve endpoint can generate a WhatsApp deep link without calling upstream services.
    monkeypatch.setenv("AFFILIATE_SKIP_LINK_TARGET_VALIDATION", "1")
    monkeypatch.setenv("AFFILIATE_DEFAULT_WHATSAPP_NUMBER", "+260970000000")

    from src.app.db import get_db_session
    from src.app.main import app
    from src.app.models import Affiliate, AffiliateLink, AffiliateToken

    await app.router.startup()
    try:
        affiliate_id = _uuid()
        link_code = "code-resolve-1"
        product_id = _uuid()
        business_id = _uuid()

        async with get_db_session() as db:
            db.add(Affiliate(id=affiliate_id, name="A", phone="+260900000001"))
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
            r = await ac.get(f"/a/{link_code}/resolve")

        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "available"
        assert body["whatsapp_url"].startswith("https://wa.me/260970000000?text=")
        assert body["token_message"].startswith("ace:")
        assert isinstance(body["token"], str) and len(body["token"]) >= 10

        # Token is persisted.
        async with get_db_session() as db:
            token_row = (await db.execute(select(AffiliateToken).where(AffiliateToken.token == body["token"])) ).scalar_one_or_none()
            assert token_row is not None
            assert token_row.product_id == product_id
            assert token_row.business_id == business_id
    finally:
        await app.router.shutdown()
