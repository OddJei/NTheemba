import pytest

from app.handlers.order_confirm_cart import confirm_cart


class DummyStore:
    def __init__(self, oob, ver=1):
        self._oob = oob
        self._ver = ver

    async def cas_update(self, session_id, updater, max_retries=3):
        new = updater(self._oob)
        # simulate version increment
        self._oob = new
        self._ver += 1
        return self._oob, self._ver


@pytest.mark.asyncio
async def test_confirm_cart_empty():
    oob = {"cart": {"items": []}}
    store = DummyStore(oob)
    res_oob, ver = await confirm_cart(store=store, session_id="s1")
    assert res_oob.get("last_validation_error") == "no_items"
    assert res_oob.get("last_node_executed") == "order.confirm_cart"


@pytest.mark.asyncio
async def test_confirm_cart_valid():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}]}}
    store = DummyStore(oob)
    res_oob, ver = await confirm_cart(store=store, session_id="s1", event_id="e1")
    assert res_oob.get("cart", {}).get("status") == "ready_for_review"
    assert res_oob.get("last_node_executed") == "order.confirm_cart"
    assert res_oob.get("last_event_id") == "e1"
