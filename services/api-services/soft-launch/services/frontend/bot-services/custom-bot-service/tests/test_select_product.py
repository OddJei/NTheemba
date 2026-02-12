import pytest

from app.handlers.browse_catalogue_select_product import select_product


class DummyStoreCAS:
    def __init__(self, oob):
        self._oob = oob

    async def cas_update(self, session_id, updater):
        new = updater(self._oob)
        self._oob = new
        return new, 2


class DummyIce:
    async def get_product(self, session_id: str, product_id: str):
        return {"product_id": product_id, "name": "Apples", "price": 1000}

    async def hydrate(self, *, session_id: str, required_blobs: list[str], event_id: str | None = None):
        out = {}
        for k in required_blobs:
            if k.startswith("product:"):
                pid = k.split(":", 1)[1]
                out[k] = {"product_id": pid, "name": "Apples", "price": 1000}
            else:
                out[k] = None
        return out


@pytest.mark.asyncio
async def test_select_product_updates_oob_and_calls_ice():
    oob = {"meta": {}}
    store = DummyStoreCAS(oob)
    ice = DummyIce()
    new, ver = await select_product(store=store, session_id="s1", product_id="p1", product_name="Apples", ice_client=ice)
    assert new["meta"]["selected_product"]["id"] == "p1"
    assert new["meta"]["selected_product"]["name"] == "Apples"
