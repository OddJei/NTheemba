import pytest

from app.handlers.browse_catalogue_serve_categories import serve_categories


class DummyStore:
    def __init__(self, oob):
        self._oob = oob

    async def create_default_if_missing(self, session_id):
        return self._oob, 1


class DummyIce:
    async def get_categories(self, session_id: str):
        return {"categories": [{"id": "c1", "name": "Fruits"}, {"id": "c2", "name": "Bakery"}]}

    async def hydrate(self, *, session_id: str, required_blobs: list[str], event_id: str | None = None):
        # support resolver.hydrate contract used by resolver
        out = {}
        for k in required_blobs:
            if k == "categories":
                out[k] = [{"id": "c1", "name": "Fruits"}, {"id": "c2", "name": "Bakery"}]
            else:
                out[k] = None
        return out


@pytest.mark.asyncio
async def test_browse_without_ice_no_meta():
    store = DummyStore({})
    res = await serve_categories(store=store, session_id="s1")
    assert "don't have categories" in res["reply_text"].lower()
    assert res["categories"] == []


@pytest.mark.asyncio
async def test_browse_with_ice():
    store = DummyStore({})
    ice = DummyIce()
    res = await serve_categories(store=store, session_id="s1", ice_client=ice)
    assert "categories" in res
    assert isinstance(res["categories"], list)
    assert len(res["categories"]) == 2
