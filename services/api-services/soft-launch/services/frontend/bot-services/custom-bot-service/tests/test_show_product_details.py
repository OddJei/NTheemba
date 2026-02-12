import pytest

from app.handlers.browse_catalogue_show_product_details import show_product_details


class DummyStore:
    def __init__(self, oob):
        self._oob = oob

    async def create_default_if_missing(self, session_id):
        return self._oob, 1


class DummyIce:
    async def get_product(self, session_id: str, product_id: str):
        return {"product_id": product_id, "name": "Apples", "price": 1000, "currency": "ZMW", "description": "Fresh apples"}

    async def hydrate(self, *, session_id: str, required_blobs: list[str], event_id: str | None = None):
        # support resolver hydration API for backward compatibility in tests
        out = {}
        for b in required_blobs:
            if b.startswith("product:"):
                pid = b.split(":", 1)[1]
                out[b] = {"product_id": pid, "name": "Apples", "price": 1000, "currency": "ZMW", "description": "Fresh apples"}
            else:
                out[b] = None
        return out


@pytest.mark.asyncio
async def test_show_product_details_from_ice():
    store = DummyStore({})
    ice = DummyIce()
    res = await show_product_details(store=store, session_id="s1", product_id="p1", ice_client=ice)
    assert "Apples" in res["reply_text"]
    assert res["product"]["product_id"] == "p1"


@pytest.mark.asyncio
async def test_show_product_details_not_found():
    store = DummyStore({})
    res = await show_product_details(store=store, session_id="s1", product_name="Nonexistent")
    assert "couldn't find" in res["reply_text"].lower()
