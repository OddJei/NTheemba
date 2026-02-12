from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure `app` package is importable when running pytest from the service folder.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models.schemas import IntentRequest
from app.services.intent_service import service


@pytest.mark.asyncio
async def test_deterministic_add_item_quantity_slot():
    req = IntentRequest(
        event_id="evt_1",
        session_id="sess_1",
        bot_id="bot_1",
        bot_type="default",
        raw_text="I want to buy 2 solar panels",
        enriched_meta={"current_node": "serve_products"},
    )

    res = await service.resolve(req)

    assert res.event_id == "evt_1"
    assert res.session_id == "sess_1"
    assert res.intent.id in {"add_item", "unknown"}
    assert isinstance(res.slots, dict)
    assert res.slots.get("quantity") == 2
    assert res.next_action in {"reply", "outbound", "none"}


@pytest.mark.asyncio
async def test_unknown_intent_falls_back():
    req = IntentRequest(
        event_id="evt_2",
        session_id="sess_2",
        raw_text="blargh zzzzz",
        enriched_meta={},
    )

    res = await service.resolve(req)
    assert res.intent.id in {"unknown", "add_item", "track_order", "cancel_order", "request_support"}
    assert "fallback" in (res.diagnostics or {})
