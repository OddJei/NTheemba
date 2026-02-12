import pytest

from app.handlers.affiliate_capture_code import capture_code
from app.handlers.affiliate_track_click import track_click


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
    async def track_affiliate_click(self, *, session_id: str, affiliate_code: str, source: str | None = None, event_id: str | None = None):
        return {"status": "ok", "affiliate_code": affiliate_code, "recorded": True}


@pytest.mark.asyncio
async def test_capture_code_from_payload():
    oob = {"cart": {"items": []}, "meta": {}}
    store = DummyStore(oob)
    payload = {"meta": {"affiliate_code": "AFF123", "affiliate_source": "utm"}}
    res_oob, ver = await capture_code(store=store, session_id="s1", payload=payload)
    assert res_oob.get("meta", {}).get("affiliate_code") == "AFF123"
    assert res_oob.get("meta", {}).get("affiliate_source") == "utm"


@pytest.mark.asyncio
async def test_track_click_calls_ice_and_stores_response():
    oob = {"cart": {"items": []}, "meta": {"affiliate_code": "AFF123", "affiliate_source": "link"}}
    store = DummyStore(oob)
    ice = DummyIce()
    res_oob, ver = await track_click(store=store, session_id="s1", ice_client=ice)
    assert res_oob.get("meta", {}).get("affiliate_last_track", {}).get("status") == "ok"
