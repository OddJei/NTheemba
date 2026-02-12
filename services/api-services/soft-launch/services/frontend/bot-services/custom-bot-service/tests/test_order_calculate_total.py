import pytest

from app.handlers.order_calculate_total import calculate_total


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
    async def price_cart(self, session_id, oob_ref, event_id=None):
        return {"subtotal": 1200, "tax": 120, "discount": 0, "grand_total": 1320, "lines": [{"product_id": "p123", "unit_price": 600, "quantity": 2, "line_total": 1200}]}


class DummyIceClientRaises:
    async def price_cart(self, session_id, oob_ref, event_id=None):
        raise RuntimeError("ICE down")


@pytest.mark.asyncio
async def test_calculate_total_success():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}]}}
    store = DummyStore(oob)
    res_oob, ver = await calculate_total(store=store, session_id="s1", event_id="e1", ice_client=DummyIceClient())
    assert res_oob.get("cart", {}).get("totals", {}).get("grand_total") == 1320
    assert res_oob.get("cart", {}).get("status") == "priced"
    assert res_oob.get("last_node_executed") == "order.calculate_total"


@pytest.mark.asyncio
async def test_calculate_total_failure():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}]}}
    store = DummyStore(oob)
    res_oob, ver = await calculate_total(store=store, session_id="s1", event_id="e1", ice_client=DummyIceClientRaises())
    assert res_oob.get("last_validation_error") == "pricing_failed"
    assert res_oob.get("last_node_executed") == "order.calculate_total"
