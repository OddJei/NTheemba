import asyncio
import sys
import os
import pytest

def _add_import_path():
    root = os.getcwd()
    svc = os.path.join(root, "services", "frontend", "bot-services", "custom-bot-service")
    if svc not in sys.path:
        sys.path.insert(0, svc)


_add_import_path()

from app import runtime_engine as re


class FakeOOBStore:
    def __init__(self):
        self._data = {}
        self._versions = {}

    async def get_oob(self, session_id: str):
        o = self._data.get(session_id)
        if o is None:
            o = {"cart": {"items": [], "totals": {}, "status": "building", "cart_version": 1}, "meta": {}}
            self._data[session_id] = o
            self._versions[session_id] = 1
        return self._data[session_id], self._versions.get(session_id, 1)

    async def cas_update(self, session_id: str, updater, max_retries: int = 3):
        current = self._data.get(session_id, {"cart": {"items": [], "totals": {}, "status": "building", "cart_version": 1}, "meta": {}})
        new = updater(current)
        if asyncio.iscoroutine(new):
            new = await new
        self._data[session_id] = new
        self._versions[session_id] = self._versions.get(session_id, 1) + 1
        return new, self._versions[session_id]


class FakeIce:
    def __init__(self):
        self.enabled = True
        self.last_update = None

    async def hydrate(self, session_id: str, required_blobs: list[str], event_id: str | None = None):
        # return delivery locations
        return {required_blobs[0]: [{"town_name": "Lusaka", "delivery_price": 10}, {"town_name": "Ndola", "delivery_price": 20}]}

    async def update_stage(self, session_id: str, cycle_id: str | None, new_stage: str, context: dict | None = None, event_id: str | None = None):
        self.last_update = {"session_id": session_id, "cycle_id": cycle_id, "new_stage": new_stage, "context": context}
        return {"cycle_id": f"cycle-{new_stage}-1", "hydrated_blobs": {}}


@pytest.mark.asyncio
async def test_payment_delivery_integration(monkeypatch):
    store = FakeOOBStore()
    ice = FakeIce()
    session_id = "pay-int-1"

    # monkeypatch start_cycle to avoid Redis
    async def fake_start_cycle(sid, ctype, **kw):
        return {"session_id": sid, "cycle_type": ctype}

    monkeypatch.setattr(re, "start_cycle", fake_start_cycle)

    # pre-populate cart and totals
    await store.cas_update(session_id, lambda o: {**o, "cart": {"items": [{"product_name": "Bread", "quantity": 1, "price": 50}], "totals": {"grand_total": 60}, "status": "priced"}})

    # simulate user providing inputs in one turn
    payload = {"text": "260971234567 delivery Lusaka 123 Main Street"}
    towns = await re.fetch_business_delivery_locations(ice_client=ice, session_id=session_id)
    inputs = await re.collect_payment_inputs_one_turn(payload=payload, available_towns=towns)
    errors = re.validate_payment_inputs(phone=inputs.get("phone"), delivery_option=inputs.get("delivery_option"), town=inputs.get("town"), available_towns=towns)
    assert errors == {}

    # transition to delivery
    reply = await re.transition_to_delivery(store=store, session_id=session_id, cycle_id=None, order_id="order-1", payment_phone=inputs.get("phone"), delivery_option=inputs.get("delivery_option"), delivery_town=inputs.get("town"), delivery_address=inputs.get("address"), event_id="evt", ice_client=ice)
    assert reply.get("persona") == "NTheemba"
    assert ice.last_update and ice.last_update.get("new_stage") == "delivery"
