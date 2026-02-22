import pytest

from app.adapters.msme import MsmeEngineAdapter


class DummyResp:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload


class DummySession:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        return self._resp


@pytest.mark.asyncio
async def test_fetch_business_delivery_locations_mapping(monkeypatch):
    payload = {"Lusaka": {"price_minor": 2500}, "Kitwe": {"price_minor": 1800}}
    resp = DummyResp(200, payload)
    adapter = MsmeEngineAdapter(base_url="http://msme")

    monkeypatch.setattr(adapter, "_get_session", lambda: DummySession(resp))

    res = await adapter.fetch_business_delivery_locations("b1")
    assert isinstance(res, list)
    assert any(r.get("name") == "Lusaka" for r in res)


@pytest.mark.asyncio
async def test_fetch_business_delivery_locations_list(monkeypatch):
    payload = [{"id": "loc1", "name": "Kitwe", "price_minor": 1800}]
    resp = DummyResp(200, payload)
    adapter = MsmeEngineAdapter(base_url="http://msme")
    monkeypatch.setattr(adapter, "_get_session", lambda: DummySession(resp))

    res = await adapter.fetch_business_delivery_locations("b2")
    assert isinstance(res, list)
    assert res[0]["name"] == "Kitwe"
