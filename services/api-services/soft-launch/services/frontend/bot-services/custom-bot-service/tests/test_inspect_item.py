import pytest

from app.handlers.inspect_item import inspect_item


class DummyStore:
    def __init__(self, oob):
        self._oob = oob

    async def get_oob(self, session_id):
        return self._oob, 1


@pytest.mark.asyncio
async def test_inspect_by_name_found():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}, {"product_name": "Bananas", "quantity": 1}]}}
    store = DummyStore(oob)
    res = await inspect_item(store=store, session_id="s1", product_name="apples")
    assert res["found"] is True
    assert res["item"]["product_name"] == "Apples"
    assert res["index"] == 0


@pytest.mark.asyncio
async def test_inspect_by_index_found():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}, {"product_name": "Bananas", "quantity": 1}]}}
    store = DummyStore(oob)
    res = await inspect_item(store=store, session_id="s1", line_index=1)
    assert res["found"] is True
    assert res["item"]["product_name"] == "Bananas"
    assert res["index"] == 1


@pytest.mark.asyncio
async def test_inspect_not_found():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}]}}
    store = DummyStore(oob)
    res = await inspect_item(store=store, session_id="s1", product_name="oranges")
    assert res["found"] is False
    assert res["item"] == {}
    assert res["index"] is None
