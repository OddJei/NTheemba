import pytest

from app.handlers.confirm_order_gate import confirm_order_gate


class DummyStore:
    def __init__(self, oob, ver=1):
        self._oob = oob
        self._ver = ver

    async def cas_update(self, session_id, updater, max_retries=3):
        new = updater(self._oob)
        self._oob = new
        self._ver += 1
        return self._oob, self._ver


class DummyIceClient:
    async def create_order(self, session_id, oob_ref, event_id=None):
        return {"order_id": "ord_123", "status": "created"}


class DummyIceClientRaises:
    async def create_order(self, session_id, oob_ref, event_id=None):
        raise RuntimeError("ICE down")


@pytest.mark.asyncio
async def test_confirm_order_wrong_phrase():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}]}}
    store = DummyStore(oob)
    res_oob, ver = await confirm_order_gate(store=store, session_id="s1", raw_text="please confirm")
    assert res_oob.get("last_validation_error") == "confirm_phrase_required"


@pytest.mark.asyncio
async def test_confirm_order_success():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}]}, "meta": {}}
    store = DummyStore(oob)
    res_oob, ver = await confirm_order_gate(store=store, session_id="s1", raw_text="CONFIRM ORDER", event_id="e1", ice_client=DummyIceClient())
    assert res_oob.get("meta", {}).get("order_id") == "ord_123"
    assert res_oob.get("cart", {}).get("status") == "order_created"


@pytest.mark.asyncio
async def test_confirm_order_ice_failure():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}]}}
    store = DummyStore(oob)
    res_oob, ver = await confirm_order_gate(store=store, session_id="s1", raw_text="CONFIRM ORDER", event_id="e1", ice_client=DummyIceClientRaises())
    assert res_oob.get("last_validation_error") == "order_create_failed"
