import pytest

from app.ice_client import IceClient
from app.handlers.confirm_order_gate import confirm_order_gate
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


@pytest.mark.asyncio
async def test_confirm_flow_with_mock_ice():
    oob = {"cart": {"items": [{"product_name": "Apples", "quantity": 2}]}, "meta": {}}
    store = DummyStore(oob)

    ice = IceClient(base_url="http://ice.internal")

    async def _fake_post(path, json):
        # simple dispatcher for the mock ICE
        if path == "/ice/order/create":
            return {"order_id": "ord_int_1", "status": "created"}
        if path == "/ice/payment/trigger":
            return {"payment_id": "pay_int_1", "status": "initiated"}
        raise RuntimeError("unexpected path")

    # monkeypatch the instance method
    ice._post = _fake_post

    # confirm order (should call our fake_post and set order_id)
    res_oob, ver = await confirm_order_gate(store=store, session_id="s1", raw_text="CONFIRM ORDER", event_id="e1", ice_client=ice)
    assert res_oob.get("meta", {}).get("order_id") == "ord_int_1"
    assert res_oob.get("cart", {}).get("status") == "order_created"

    # confirm payment (should call our fake_post and set payment_id)
    res_oob2, ver2 = await confirm_payment_gate(store=store, session_id="s1", raw_text="CONFIRM PAYMENT", event_id="e2", ice_client=ice)
    assert res_oob2.get("meta", {}).get("payment_id") == "pay_int_1"
    assert res_oob2.get("meta", {}).get("payment_status") == "initiated"
