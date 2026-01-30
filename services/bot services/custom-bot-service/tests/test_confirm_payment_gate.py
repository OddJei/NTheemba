import pytest

from app.handlers.confirm_payment_gate import confirm_payment_gate


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
    async def trigger_payment(self, session_id, oob_ref, event_id=None):
        return {"payment_id": "pay_1", "status": "initiated"}


class DummyIceClientRaises:
    async def trigger_payment(self, session_id, oob_ref, event_id=None):
        raise RuntimeError("ICE down")


@pytest.mark.asyncio
async def test_confirm_payment_wrong_phrase():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}]}}
    store = DummyStore(oob)
    res_oob, ver = await confirm_payment_gate(store=store, session_id="s1", raw_text="pay now")
    assert res_oob.get("last_validation_error") == "confirm_phrase_required"


@pytest.mark.asyncio
async def test_confirm_payment_success():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}]}, "meta": {}}
    store = DummyStore(oob)
    res_oob, ver = await confirm_payment_gate(store=store, session_id="s1", raw_text="CONFIRM PAYMENT", event_id="e1", ice_client=DummyIceClient())
    assert res_oob.get("meta", {}).get("payment_id") == "pay_1"
    assert res_oob.get("meta", {}).get("payment_status") == "initiated"
    assert res_oob.get("cart", {}).get("status") == "payment_initiated"


@pytest.mark.asyncio
async def test_confirm_payment_ice_failure():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}]}}
    store = DummyStore(oob)
    res_oob, ver = await confirm_payment_gate(store=store, session_id="s1", raw_text="CONFIRM PAYMENT", event_id="e1", ice_client=DummyIceClientRaises())
    assert res_oob.get("last_validation_error") == "payment_trigger_failed"
