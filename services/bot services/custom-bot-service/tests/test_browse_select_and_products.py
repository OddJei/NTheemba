import pytest

from app.handlers.browse_catalogue_select_category import select_category
from app.handlers.browse_catalogue_serve_products import serve_products


class DummyStoreCAS:
    def __init__(self, oob):
        self._oob = oob

    async def cas_update(self, session_id, updater):
        new = updater(self._oob)
        self._oob = new
        return new, 2

    async def create_default_if_missing(self, session_id):
        return self._oob, 1


class DummyIce:
    async def get_products(self, session_id: str, category: str):
        return {"products": [{"id": "p1", "name": "Apples"}, {"id": "p2", "name": "Bananas"}]}

    async def hydrate(self, *, session_id: str, required_blobs: list[str], event_id: str | None = None):
        out = {}
        for b in required_blobs:
            if b.startswith("products:category:"):
                out[b] = {"products": [{"id": "p1", "name": "Apples"}, {"id": "p2", "name": "Bananas"}]}
            else:
                out[b] = None
        return out


@pytest.mark.asyncio
async def test_select_category_updates_oob():
    oob = {"meta": {}}
    store = DummyStoreCAS(oob)
    new, ver = await select_category(store=store, session_id="s1", category_id="c1", category_name="Fruits")
    assert new["meta"]["selected_category"]["id"] == "c1"
    assert new["meta"]["selected_category"]["name"] == "Fruits"


@pytest.mark.asyncio
async def test_serve_products_with_ice():
    oob = {"meta": {"selected_category": {"id": "c1", "name": "Fruits"}}}
    store = DummyStoreCAS(oob)
    ice = DummyIce()
    res = await serve_products(store=store, session_id="s1", ice_client=ice)
    assert isinstance(res["products"], list)
    assert len(res["products"]) == 2
