import asyncio
import pytest

from app.resolver import resolve_required_blobs


class DummyStore:
    def __init__(self):
        self._oob = {"meta": {}}

    async def create_default_if_missing(self, session_id):
        return self._oob, 1

    async def cas_update(self, session_id, updater):
        self._oob = updater(self._oob)
        return self._oob, 2


class CountingIce:
    def __init__(self):
        self.calls = 0

    async def hydrate(self, *, session_id: str, required_blobs: list[str], event_id: str | None = None):
        self.calls += 1
        # simulate work
        await asyncio.sleep(0.05)
        out = {}
        for k in required_blobs:
            out[k] = {"id": k, "value": "x"}
        return out


@pytest.mark.asyncio
async def test_single_flight_hydration_calls_once():
    store = DummyStore()
    ice = CountingIce()

    async def task():
        return await resolve_required_blobs(store=store, session_id="s1", required_blobs=["product:p1"], ice_client=ice)

    results = await asyncio.gather(task(), task())
    assert results[0]["product:p1"]["id"] == "product:p1"
    assert results[1]["product:p1"]["id"] == "product:p1"
    assert ice.calls == 1
