import pytest

from app.handlers.order_check_stock import check_stock


class DummyStore:
    def __init__(self, oob):
        self._oob = oob

    async def create_default_if_missing(self, session_id):
        return self._oob, 1

    async def cas_update(self, session_id, updater):
        new = updater(self._oob)
        self._oob = new
        return self._oob, 2


class DummyIceOK:
    async def check_stock(self, session_id: str, items: list[dict]):
        return {"items": [{"product_id": it.get("product_id") or "p1", "available": True} for it in items]}


class DummyIceFail:
    async def check_stock(self, session_id: str, items: list[dict]):
        return {"items": [{"product_id": it.get("product_id") or "p1", "available": False} for it in items]}


@pytest.mark.asyncio
async def test_check_stock_success():
    oob = {"cart": {"items": [{"product_id": "p1", "quantity": 1}]}, "meta": {}}
    store = DummyStore(oob)
    ice = DummyIceOK()
    res_oob, ver = await check_stock(store=store, session_id="s1", ice_client=ice)
    assert res_oob.get("last_validation_error") is None
    assert res_oob.get("meta", {}).get("stock_check") is not None


@pytest.mark.asyncio
async def test_check_stock_unavailable():
    oob = {"cart": {"items": [{"product_id": "p1", "quantity": 1}]}, "meta": {}}
    store = DummyStore(oob)
    ice = DummyIceFail()
    res_oob, ver = await check_stock(store=store, session_id="s1", ice_client=ice)
    assert res_oob.get("last_validation_error") == "out_of_stock"
    assert res_oob.get("meta", {}).get("stock_check") is not None
