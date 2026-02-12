import os
import sys
import asyncio


def _add_app_path():
    here = os.path.dirname(__file__)
    app_dir = os.path.normpath(os.path.join(here, "..", "app"))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)


_add_app_path()

import runtime_engine as engine  # type: ignore


class DummyStore:
    def __init__(self, oob=None):
        self._oob = oob or {"meta": {}, "cart": {"items": []}}
        self._ver = 1

    async def create_default_if_missing(self, session_id):
        return (self._oob, self._ver)

    async def get_oob(self, session_id):
        return (self._oob, self._ver)

    async def cas_update(self, session_id, updater, max_retries=3):
        self._oob = updater(self._oob)
        self._ver += 1
        return (self._oob, self._ver)

    async def set_last_event(self, session_id, event_id):
        return True


class DummyIce:
    def __init__(self):
        self.enabled = True
        self.update_calls = []
        self.create_calls = []
        self.payment_calls = []

    async def update_stage(self, *, session_id, cycle_id=None, new_stage, context=None, event_id=None):
        self.update_calls.append({"session_id": session_id, "cycle_id": cycle_id, "new_stage": new_stage, "context": context, "event_id": event_id})
        return {"cycle_id": cycle_id or "cycle-1", "hydrated_blobs": {}}

    async def create_order(self, *, session_id, oob_ref, event_id=None, extra=None):
        self.create_calls.append({"session_id": session_id, "oob_ref": oob_ref, "event_id": event_id, "extra": extra})
        return {"order_id": "ord-100", "status": "created"}

    async def trigger_payment(self, *, session_id, oob_ref, event_id=None, payment_method=None):
        self.payment_calls.append({"session_id": session_id, "oob_ref": oob_ref, "event_id": event_id, "payment_method": payment_method})
        return {"payment_id": "pay-100", "status": "initiated"}

    async def price_cart(self, *, session_id, oob_ref, event_id=None):
        return {"grand_total": 90}

    async def check_stock(self, *, session_id, items):
        return {"items": [{"available": True} for _ in items]}


async def _run_full_flow():
    store = DummyStore({
        "meta": {},
        "cart": {
            "items": [{"product_id": "p1", "product_name": "Bread", "quantity": 2, "price": 30}],
            "totals": {},
            "status": "building",
        },
    })
    ice = DummyIce()

    # confirm cart -> order stage
    new_cid, _ = await engine.confirm_cart_and_initiate_order(
        store=store,
        session_id="sess-1",
        cycle_id=None,
        current_stage="cart",
        event_id="evt-1",
        ice_client=ice,
        raw_text="confirm cart",
    )
    assert ice.update_calls and ice.update_calls[0]["new_stage"] == "order"
    assert ice.update_calls[0]["context"].get("checkout") is True

    # validate/review order (stock + totals)
    review, _snapshot = await engine.validate_and_review_order(store=store, session_id="sess-1", event_id="evt-2", ice_client=ice)
    assert review.get("ready_to_confirm") is True

    # confirm order -> payment stage
    await engine.confirm_order_gate(store=store, session_id="sess-1", event_id="evt-3", raw_text="CONFIRM ORDER", ice_client=ice)
    order_id = (store._oob.get("meta") or {}).get("order_id")
    assert order_id == "ord-100"

    await engine.transition_to_payment(store=store, session_id="sess-1", cycle_id=new_cid, order_id=order_id, event_id="evt-4", ice_client=ice)
    assert any(call["new_stage"] == "payment" for call in ice.update_calls)

    # collect payment inputs and validate
    payload = {"text": "260977123456 delivery Lusaka Plot 12"}
    available_towns = [{"town_name": "Lusaka", "delivery_price": 1500}]
    inputs = await engine.collect_payment_inputs_one_turn(payload=payload, available_towns=available_towns)
    errors = engine.validate_payment_inputs(
        phone=inputs.get("payment_phone"),
        delivery_option=inputs.get("delivery_option"),
        town=inputs.get("delivery_town"),
        address=inputs.get("delivery_address"),
        available_towns=available_towns,
    )
    assert errors == {}

    # persist payment inputs
    def _upd(oob):
        o = dict(oob)
        meta = dict(o.get("meta") or {})
        meta["payment_phone"] = inputs.get("payment_phone")
        meta["delivery_option"] = inputs.get("delivery_option")
        meta["delivery_location"] = {
            "town": inputs.get("delivery_town"),
            "address": inputs.get("delivery_address"),
        }
        o["meta"] = meta
        return o

    await store.cas_update("sess-1", _upd)

    # confirm payment -> delivery stage
    await engine.confirm_payment_gate(store=store, session_id="sess-1", event_id="evt-5", raw_text="CONFIRM PAYMENT", ice_client=ice)
    reply = await engine.transition_to_delivery(
        store=store,
        session_id="sess-1",
        cycle_id=new_cid,
        order_id=order_id,
        payment_phone=inputs.get("payment_phone"),
        delivery_option=inputs.get("delivery_option"),
        delivery_town=inputs.get("delivery_town"),
        delivery_address=inputs.get("delivery_address"),
        event_id="evt-6",
        ice_client=ice,
    )
    assert any(call["new_stage"] == "delivery" for call in ice.update_calls)
    assert reply.get("render_type") == "direct_gemini"
    assert reply.get("persona") == "NTheemba"
    assert order_id in reply.get("text", "")

    # OOB context snapshot checks
    meta = store._oob.get("meta") or {}
    assert meta.get("order_id") == order_id
    assert meta.get("payment_phone") == inputs.get("payment_phone")
    assert meta.get("delivery_location", {}).get("town") == "Lusaka"


def test_pipeline_end_to_end():
    asyncio.run(_run_full_flow())
