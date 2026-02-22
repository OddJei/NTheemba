import asyncio
import json
import pytest

import httpx

from src.app.main import _get_business_delivery_locations


class DummyResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class DummyClient:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        return self._resp


@pytest.mark.asyncio
async def test_get_business_delivery_locations_mapping(monkeypatch):
    payload = {"Lusaka": {"price_minor": 2500, "currency": "ZMW"}}
    resp = DummyResponse(200, payload)

    async def dummy_client(*, timeout):
        return DummyClient(resp)

    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=None: DummyClient(resp))

    res = await _get_business_delivery_locations(business_id="b1")
    assert isinstance(res, list)
    assert len(res) == 1
    loc = res[0]
    assert loc.get("price_minor") == 2500
    # name should be set from mapping key when not present
    assert loc.get("name") == "Lusaka"


@pytest.mark.asyncio
async def test_get_business_delivery_locations_list(monkeypatch):
    payload = [{"id": "loc1", "name": "Kitwe", "price_minor": 1800}]
    resp = DummyResponse(200, payload)
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=None: DummyClient(resp))

    res = await _get_business_delivery_locations(business_id="b2")
    assert isinstance(res, list)
    assert len(res) == 1
    assert res[0]["name"] == "Kitwe"


@pytest.mark.asyncio
async def test_get_business_delivery_locations_unreachable(monkeypatch):
    async def raiser(*, timeout):
        raise httpx.RequestError("boom")

    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=None: (_ for _ in ()).throw(httpx.RequestError("boom")))

    res = await _get_business_delivery_locations(business_id="b3")
    assert res == []
