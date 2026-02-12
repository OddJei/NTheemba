import asyncio
import json

import pytest

from app.oob_store import OOBStore, DEFAULT_OOB, VersionConflict


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self._watch_key = None
        self._multi = False
        self._mapping = None

    async def watch(self, key):
        self._watch_key = key

    async def unwatch(self):
        self._watch_key = None

    def multi(self):
        self._multi = True

    def hset(self, key, mapping=None):
        self._mapping = (key, mapping)

    async def execute(self):
        # Apply mapping to underlying store
        if self._mapping:
            key, mapping = self._mapping
            self.redis._store[key] = mapping
        return True

    async def reset(self):
        self._watch_key = None
        self._multi = False
        self._mapping = None


class FakeRedis:
    def __init__(self):
        self._store = {}

    async def hgetall(self, key):
        return self._store.get(key, {})

    async def exists(self, key):
        return 1 if key in self._store else 0

    async def hset(self, key, mapping=None):
        self._store[key] = mapping or {}

    async def hget(self, key, field):
        return (self._store.get(key, {}) or {}).get(field)

    def pipeline(self):
        return FakePipeline(self)

    # expose exceptions namespace used in oob_store
    class exceptions:
        class WatchError(Exception):
            pass


@pytest.mark.asyncio
async def test_create_default_and_get_oob():
    fake = FakeRedis()
    store = OOBStore(redis_url=None)
    store._r = fake

    payload, ver = await store.create_default_if_missing("s1")
    assert ver == 1
    assert payload.get("schema_version") == DEFAULT_OOB["schema_version"]

    fetched, ver2 = await store.get_oob("s1")
    assert ver2 == 1
    assert fetched["cart"]["status"] == "building"


@pytest.mark.asyncio
async def test_cas_update_applies_mapping():
    fake = FakeRedis()
    store = OOBStore(redis_url=None)
    store._r = fake

    # initialize
    await store.create_default_if_missing("s2")

    async def updater(oob):
        o = dict(oob)
        m = dict(o.get("meta") or {})
        m["hydrated_blobs"] = {"product:p1": {"id": "p1", "name": "Bread"}}
        o["meta"] = m
        return o

    new_oob, new_ver = await store.cas_update("s2", updater)
    assert new_ver >= 1
    assert (new_oob.get("meta") or {}).get("hydrated_blobs")


@pytest.mark.asyncio
async def test_cas_update_contention_retries():
    fake = FakeRedis()
    store = OOBStore(redis_url=None)
    store._r = fake

    await store.create_default_if_missing("s3")

    # Simulate an external concurrent update by modifying store between read and execute
    original_pipeline = FakePipeline

    class RacingPipeline(FakePipeline):
        async def execute(self):
            # Simulate other writer bumping version
            self.redis._store[self._watch_key]["version"] = 99
            raise fake.exceptions.WatchError()

    try:
        store._r.pipeline = lambda: RacingPipeline(store._r)

        async def updater(oob):
            o = dict(oob)
            o["meta"] = {"x": 1}
            return o

        with pytest.raises(VersionConflict):
            await store.cas_update("s3", updater, max_retries=1)
    finally:
        store._r.pipeline = lambda: original_pipeline(store._r)
