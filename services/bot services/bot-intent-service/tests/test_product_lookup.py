from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure `app` package is importable when running pytest from the service folder.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.product_lookup import lookup_products_from_request
from app.models.schemas import IntentRequest


@pytest.mark.asyncio
async def test_lookup_from_context_snapshot():
    req = IntentRequest(
        event_id="e1",
        session_id="s1",
        raw_text="I want juice",
        context={
            "catalog_snapshot": [
                {"product_id": "prd_apple_juice", "name": "Apple Juice", "aliases": ["juice", "apple juice"]},
                {"product_id": "prd_orange_juice", "name": "Orange Juice", "aliases": ["orange juice"]},
            ]
        },
    )

    snap = await lookup_products_from_request(req)
    assert isinstance(snap, list)
    assert any(p["product_id"] == "prd_apple_juice" for p in snap)


@pytest.mark.asyncio
async def test_lookup_no_snapshot_returns_empty():
    req = IntentRequest(event_id="e2", session_id="s2", raw_text="hi")
    snap = await lookup_products_from_request(req)
    assert snap == []
