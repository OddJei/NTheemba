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
    def __init__(self):
        self._data = {}

    async def create_default_if_missing(self, session_id):
        return ({"meta": {}}, 1)

    async def cas_update(self, session_id, updater):
        # naive: call updater on empty oob
        oob = {"meta": {}}
        updated = updater(oob)
        return (updated, 1)

    async def set_last_event(self, session_id, event_id):
        return True


class DummyIce:
    def __init__(self):
        self.enabled = False


def test_missing_slots_nlg_flow():
    # Patch runtime dependencies
    engine.OOBStore = DummyStore
    engine.IceClient = DummyIce

    async def fake_render_reply(template_id, template_vars):
        # echo a clear phrase so assertions are deterministic
        missing = template_vars.get("missing_slots") or []
        if missing:
            return "Please provide " + ", ".join(missing) + "."
        return "OK"

    engine.render_reply = fake_render_reply

    payload = {"meta": {"session": {"stage": "cart"}}, "text": "I want to buy"}

    res = asyncio.run(engine.process_event(payload=payload, event_id="evt-test", session_id="sess-test"))

    assert isinstance(res, dict)
    assert res.get("render_type") == "nlg"
    tpl_vars = res.get("template_vars") or {}
    assert "missing_slots" in tpl_vars
    assert "product_id" in tpl_vars.get("missing_slots")
    assert res.get("reply_text") == "Please provide product_id."
