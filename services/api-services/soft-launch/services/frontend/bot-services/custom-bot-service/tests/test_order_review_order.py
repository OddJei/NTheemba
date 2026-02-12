import pytest

from app.handlers.order_review_order import review_order


class DummyStore:
    def __init__(self, oob, ver=1):
        self._oob = oob
        self._ver = ver

    async def get_oob(self, session_id):
        return self._oob, self._ver


@pytest.mark.asyncio
async def test_review_order_empty():
    oob = {"cart": {"items": []}}
    store = DummyStore(oob)
    res = await review_order(store=store, session_id="s1")
    assert res["items_count"] == 0
    assert res["ready_to_confirm"] is False


@pytest.mark.asyncio
async def test_review_order_with_totals():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}], "totals": {"grand_total": 1320}}}
    store = DummyStore(oob)
    res = await review_order(store=store, session_id="s1")
    assert res["items_count"] == 1
    assert res["ready_to_confirm"] is True
    assert res["totals"]["grand_total"] == 1320
