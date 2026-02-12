import pytest

from app.handlers.order_validate_items import validate_items


class DummyStore:
    def __init__(self, oob):
        self._oob = oob

    async def create_default_if_missing(self, session_id):
        return self._oob, 1

    async def cas_update(self, session_id, updater):
        new = updater(self._oob)
        self._oob = new
        return self._oob, 2


@pytest.mark.asyncio
async def test_validate_items_missing_product_ref():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}]}, "meta": {}}
    store = DummyStore(oob)
    res_oob, ver = await validate_items(store=store, session_id="s1")
    assert res_oob.get("last_validation_error") == "invalid_items"
    probs = res_oob.get("meta", {}).get("validation_problems")
    assert isinstance(probs, list) and probs[0]["error"] == "missing_product_ref"


@pytest.mark.asyncio
async def test_validate_items_success():
    oob = {"cart": {"items": [{"product_id": "p1", "quantity": 1}]}, "meta": {}}
    store = DummyStore(oob)
    res_oob, ver = await validate_items(store=store, session_id="s1")
    assert res_oob.get("last_validation_error") is None
    assert res_oob.get("meta", {}).get("validation_problems") is None
