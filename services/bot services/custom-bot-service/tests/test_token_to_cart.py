import pytest

from app import runtime_engine


@pytest.mark.asyncio
async def test_token_resolves_and_adds_to_cart(monkeypatch):
    # Ensure ICE appears enabled to the runtime
    monkeypatch.setattr(runtime_engine.IceClient, "enabled", True, raising=False)

    async def fake_resolve_token(self, *, token, buyer_phone=None, session_id=None, event_id=None):
        return {"id": "p1", "name": "Cool Product", "price": 199, "affiliate_id": "aff1", "campaign": "summer"}

    monkeypatch.setattr(runtime_engine.IceClient, "resolve_token", fake_resolve_token)

    # Prevent real Redis usage in OOBStore ctor
    def fake_oob_init(self, redis_url=None):
        self._r = None

    monkeypatch.setattr(runtime_engine.OOBStore, "__init__", fake_oob_init)

    async def fake_cas_update(self, session_id_arg, updater, max_retries=3):
        current = {"cart": {"items": []}}
        new = updater(current)
        return new, 2

    monkeypatch.setattr(runtime_engine.OOBStore, "cas_update", fake_cas_update)

    payload = {"text": "Check this ace:abc123", "from": "buyer_phone"}
    res = await runtime_engine.process_event(payload=payload, event_id="evt1", session_id="sess1")

    assert res["next_node"] == "order.review_order"
    assert "affiliate.token" in res["intent_ids"]
    assert res["oob_summary"]["items_count"] == 1
    assert res["oob_summary"]["oob_version"] == 2
    assert "Cool Product" in res["reply_text"]
