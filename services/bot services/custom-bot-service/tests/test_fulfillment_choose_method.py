import pytest

from app.handlers.fulfillment_choose_method import choose_method


class DummyStore:
    def __init__(self, oob, ver=1):
        self._oob = oob
        self._ver = ver

    async def cas_update(self, session_id, updater, max_retries=3):
        new = updater(self._oob)
        self._oob = new
        self._ver += 1
        return self._oob, self._ver

    async def get_oob(self, session_id):
        return self._oob, self._ver


class DummyIceClient:
    async def validate_fulfillment_method(self, *, session_id, method, details=None):
        return {"valid": True}


class DummyIceClientInvalid:
    async def validate_fulfillment_method(self, *, session_id, method, details=None):
        return {"valid": False}


@pytest.mark.asyncio
async def test_choose_method_missing():
    oob = {}
    store = DummyStore(oob)
    res_oob, ver = await choose_method(store=store, session_id="s1", method=None)
    assert res_oob.get("last_validation_error") == "fulfillment_method_required"


@pytest.mark.asyncio
async def test_choose_method_local_success():
    oob = {}
    store = DummyStore(oob)
    res_oob, ver = await choose_method(store=store, session_id="s1", method="delivery", details={"window":"morning"})
    assert res_oob.get("fulfillment", {}).get("method") == "delivery"
    assert res_oob.get("fulfillment", {}).get("details", {}).get("window") == "morning"


@pytest.mark.asyncio
async def test_choose_method_ice_invalid():
    oob = {}
    store = DummyStore(oob)
    res_oob, ver = await choose_method(store=store, session_id="s1", method="delivery", details={"window":"night"}, ice_client=DummyIceClientInvalid())
    assert res_oob.get("last_validation_error") == "fulfillment_method_invalid"


@pytest.mark.asyncio
async def test_choose_method_ice_success():
    oob = {}
    store = DummyStore(oob)
    res_oob, ver = await choose_method(store=store, session_id="s1", method="pickup", details={"location":"store-1"}, ice_client=DummyIceClient())
    assert res_oob.get("fulfillment", {}).get("method") == "pickup"
    assert res_oob.get("fulfillment", {}).get("details", {}).get("location") == "store-1"
