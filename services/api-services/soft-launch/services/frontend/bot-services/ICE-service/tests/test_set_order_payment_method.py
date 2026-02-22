import pytest

from app.helpers import service_helpers


class DummyResp:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload

    async def text(self):
        return str(self._payload)


class DummyCtx:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummyClient:
    def __init__(self, resp):
        self._resp = resp

    def put(self, url, json=None, headers=None):
        return DummyCtx(self._resp)


class DummyAdapter:
    def __init__(self, base_url, resp):
        self.base_url = base_url
        self._resp = resp

    async def _get_session(self):
        return DummyClient(self._resp)


@pytest.mark.asyncio
async def test_set_order_payment_method_success(monkeypatch):
    resp = DummyResp(200, {"id": "o1", "meta": {"payment_method": {"phone_number": "260761234567"}}})
    adapter = DummyAdapter("http://order", resp)
    monkeypatch.setattr(service_helpers.AdapterFactory, "get_cart_order_adapter", lambda: adapter)
    monkeypatch.setattr(service_helpers.AdapterFactory, "get_delivery_adapter", lambda: adapter)

    result = await service_helpers.set_order_payment_method("o1", "0761234567")
    assert isinstance(result, dict)
    assert result.get("id") == "o1"


@pytest.mark.asyncio
async def test_set_order_payment_method_failure(monkeypatch):
    resp = DummyResp(400, {"detail": "invalid"})
    adapter = DummyAdapter("http://order", resp)
    monkeypatch.setattr(service_helpers.AdapterFactory, "get_cart_order_adapter", lambda: adapter)
    monkeypatch.setattr(service_helpers.AdapterFactory, "get_delivery_adapter", lambda: adapter)

    result = await service_helpers.set_order_payment_method("o2", "bad")
    assert result.get("status") == "FAILED"
