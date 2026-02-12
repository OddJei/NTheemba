import pytest

from app.oob_store import OOBStore
from app.runtime_engine import upgrade_stage_if_chat, build_final_context


class DummyIce:
    def __init__(self, blobs=None, resp=None):
        self._blobs = blobs or {}

    async def update_stage(self, *, session_id, cycle_id, new_stage, context=None, event_id=None):
        return {"hydrated_blobs": self._blobs, "cycle_id": cycle_id or f"{session_id}:cart"}


@pytest.mark.asyncio
async def test_ice_hydrate_merges_into_oob_and_final_context():
    fake_redis = type("R", (), {})()
    fake_redis._store = {}

    class FR:
        def __init__(self, store):
            self._store = store

        async def hgetall(self, key):
            return self._store.get(key, {})

        async def exists(self, key):
            return 1 if key in self._store else 0

        async def hset(self, key, mapping=None):
            self._store[key] = mapping or {}

        async def hget(self, key, field):
            return (self._store.get(key, {}) or {}).get(field)

        def pipeline(self):
            # reuse simple pipeline used in unit tests
            from tests.test_oob_store import FakePipeline
            return FakePipeline(self)

        class exceptions:
            class WatchError(Exception):
                pass

    fr = FR(fake_redis._store)
    store = OOBStore(redis_url=None)
    store._r = fr

    # ensure default exists
    await store.create_default_if_missing("sess1")

    # simulate ICE returning hydrated blobs
    ice = DummyIce(blobs={"product:p1": {"id": "p1", "name": "Bread"}})

    new_cycle, blobs = await upgrade_stage_if_chat(store=store, session_id="sess1", cycle_id=None, current_stage="chat", snapshot={"user_text": "hi"}, event_id=None, ice_client=ice)
    assert blobs

    # read oob directly
    oob, ver = await store.get_oob("sess1")
    assert (oob.get("meta") or {}).get("hydrated_blobs")

    # now build final context using snapshot and stored oob
    ctx = build_final_context(snapshot={"user_text": "hi"}, mapper_results=[], store_oob=oob)
    assert ctx.get("user_text") == "hi"
