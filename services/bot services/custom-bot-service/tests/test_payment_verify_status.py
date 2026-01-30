import pytest

from app.handlers.payment_verify_status import verify_payment_status


class DummyStore:
    def __init__(self, oob, ver=1):
        self._oob = oob
        self._ver = ver

    async def get_oob(self, session_id):
        return self._oob, self._ver

    async def cas_update(self, session_id, updater, max_retries=3):
        new = updater(self._oob)
        self._oob = new
        self._ver += 1
        return self._oob, self._ver


class DummyIceClient:
    async def get_payment_status(self, *, payment_id, session_id=None):
        return {"payment_id": payment_id, "status": "paid"}


class DummyIceClientFail:
    async def get_payment_status(self, *, payment_id, session_id=None):
        raise RuntimeError("ICE failure")


@pytest.mark.asyncio
async def test_verify_payment_no_payment_id():
    oob = {"meta": {}}
    store = DummyStore(oob)
    res_oob, ver = await verify_payment_status(store=store, session_id="s1")
    assert res_oob.get("last_validation_error") == "no_payment_id"


@pytest.mark.asyncio
async def test_verify_payment_success():
    oob = {"meta": {"payment_id": "pay_1"}, "cart": {}}
    store = DummyStore(oob)
    res_oob, ver = await verify_payment_status(store=store, session_id="s1", event_id="e1", ice_client=DummyIceClient())
    assert res_oob.get("meta", {}).get("payment_status") == "paid"
    assert res_oob.get("cart", {}).get("status") == "paid"


@pytest.mark.asyncio
async def test_verify_payment_ice_failure():
    oob = {"meta": {"payment_id": "pay_2"}, "cart": {}}
    store = DummyStore(oob)
    res_oob, ver = await verify_payment_status(store=store, session_id="s1", event_id="e1", ice_client=DummyIceClientFail())
    assert res_oob.get("last_validation_error") == "payment_status_failed"
