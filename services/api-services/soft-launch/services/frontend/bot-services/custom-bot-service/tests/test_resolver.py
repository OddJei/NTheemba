import pytest

from app.resolver import resolve_required_blobs


class DummyStore:
    def __init__(self, oob):
        self._oob = oob

    async def create_default_if_missing(self, session_id):
        return self._oob, 1

    async def cas_update(self, session_id, updater):
        new = updater(self._oob)
        self._oob = new
        return self._oob, 2


class DummyIce:
    async def hydrate(self, *, session_id: str, required_blobs: list[str], event_id: str | None = None):
        out = {}
        for b in required_blobs:
            if b.startswith("product:"):
                pid = b.split(":", 1)[1]
                out[b] = {"product_id": pid, "name": "Test", "price": 100}
            else:
                out[b] = None
        return out


@pytest.mark.asyncio
async def test_resolver_hydrates_missing_product():
    oob = {"cart": {"items": []}, "meta": {}}
    store = DummyStore(oob)
    ice = DummyIce()
    res = await resolve_required_blobs(store=store, session_id="s1", required_blobs=["product:p1"], ice_client=ice)
    assert "product:p1" in res and res["product:p1"]["product_id"] == "p1"
    # ensure store got hydrated blob
    assert store._oob.get("meta", {}).get("hydrated_blobs", {}).get("product:p1") is not None


@pytest.mark.asyncio
async def test_resolver_negative_cache_for_unknown():
    oob = {"cart": {"items": []}, "meta": {}}
    store = DummyStore(oob)

    class IceNone:
        async def hydrate(self, *, session_id: str, required_blobs: list[str], event_id: str | None = None):
            return {k: None for k in required_blobs}

    ice = IceNone()
    res = await resolve_required_blobs(store=store, session_id="s1", required_blobs=["unknown:x"], ice_client=ice)
    assert res.get("unknown:x") is None
    assert store._oob.get("meta", {}).get("negative_cache", {}).get("unknown:x") is not None
