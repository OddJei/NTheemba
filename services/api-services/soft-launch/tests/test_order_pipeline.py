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

    async def update_stage(self, session_id: str, cycle_id: str | None, new_stage: str, context: dict | None = None, event_id: str | None = None):
        # simulate returning a cycle id and no hydrated blobs
        return {"cycle_id": f"cycle-{new_stage}-1", "hydrated_blobs": {}}

    async def check_stock(self, session_id: str, items: list[dict]):
        return {"items": [{"product_id": it.get("product_id") or it.get("id"), "available": True} for it in items]}

    async def price_cart(self, session_id: str, oob_ref: str, event_id: str | None = None):
        return {"subtotal": 100, "grand_total": 110}


@pytest.mark.asyncio
async def test_order_stage_flow_confirm_validate_transition_cancel(monkeypatch):
    store = FakeOOBStore()
    ice = FakeIce()
    session_id = "s-order-1"

    # monkeypatch start_cycle and complete_cycle to avoid Redis
    async def fake_start_cycle(sid, ctype, **kw):
        return {"session_id": sid, "cycle_type": ctype}

    async def fake_complete_cycle(sid, ctype, **kw):
        return {"session_id": sid, "cycle_type": ctype, "completed": True}

    monkeypatch.setattr(re, "start_cycle", fake_start_cycle)
    monkeypatch.setattr(re, "complete_cycle", fake_complete_cycle)

    # Step 0: add an item by direct cas_update
    await store.cas_update(session_id, lambda o: {**o, "cart": {"items": [{"product_name": "Bread", "quantity": 1, "price": 50}], "totals": {}, "status": "building"}})

    # Step 1: confirm cart -> initiate order stage
    cid, resp = await re.confirm_cart_and_initiate_order(store=store, session_id=session_id, cycle_id=None, current_stage="cart", event_id="evt1", ice_client=ice)
    assert cid is not None

    # Step 2: validate & review order
    review, snapshot = await re.validate_and_review_order(store=store, session_id=session_id, event_id="evt2", ice_client=ice)
    assert isinstance(review, dict)
    assert "items_count" in review

    # Step 3: transition to payment
    resp_pay = await re.transition_to_payment(store=store, session_id=session_id, cycle_id=cid, order_id="order-123", event_id="evt3", ice_client=ice)
    assert isinstance(resp_pay, dict)

    # Step 4: help
    help_reply = re.order_help()
    assert help_reply.get("persona") == "NTheemba"

    # Step 5: cancel order
    cancel_reply = await re.order_cancel(store=store, session_id=session_id, cycle_id=cid, reason="changed my mind", event_id="evt4", ice_client=ice)
    assert cancel_reply.get("persona") == "NTheemba"
