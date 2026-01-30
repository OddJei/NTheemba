import pytest

from app.handlers.greet_and_suggest import greet_and_suggest


class DummyStore:
    def __init__(self, oob):
        self._oob = oob

    async def create_default_if_missing(self, session_id):
        return self._oob, 1


class DummyIce:
    async def get_recommendations(self, session_id: str):
        return {"items": [{"id": "p1", "title": "Apples"}, {"id": "p2", "title": "Bananas"}]}

    async def hydrate(self, *, session_id: str, required_blobs: list[str], event_id: str | None = None):
        out = {}
        for k in required_blobs:
            if k == "recommendations":
                out[k] = [{"id": "p1", "title": "Apples"}, {"id": "p2", "title": "Bananas"}]
            else:
                out[k] = None
        return out


@pytest.mark.asyncio
async def test_greet_without_ice():
    store = DummyStore({})
    res = await greet_and_suggest(store=store, session_id="s1")
    assert "Hi" in res["reply_text"]
    assert res["recommendations"] == []


@pytest.mark.asyncio
async def test_greet_with_ice():
    store = DummyStore({})
    ice = DummyIce()
    res = await greet_and_suggest(store=store, session_id="s1", ice_client=ice)
    assert "recommend" in res["reply_text"].lower() or "hi" in res["reply_text"].lower()
    assert isinstance(res["recommendations"], list)
    assert len(res["recommendations"]) == 2
