import pytest

from app.helpers import service_helpers
from app.adapters.factory import AdapterFactory


class AsyncCtxResp:
    def __init__(self, status=200, json_data=None, text_data=""):
        self.status = status
        self._json = json_data or {}
        self._text = text_data

    async def json(self):
        return self._json

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_create_cart_draft_uses_adapter(monkeypatch):
    class DummyAdapter:
        order_base_url = None

        async def create_or_update_draft(self, payload):
            return {"draft_id": "d-1", "id": "d-1", "session_id": payload.get("session_id")}

    monkeypatch.setattr(AdapterFactory, "get_cart_order_adapter", classmethod(lambda cls: DummyAdapter()))

    res = await service_helpers.create_cart_draft("sess-1", "+260772000011", "biz-1", idempotency_key="key-1")
    assert res.get("draft_id") == "d-1"


@pytest.mark.asyncio
async def test_add_cart_items_calls_adapter(monkeypatch):
    class DummyAdapter:
        async def create_or_update_draft(self, payload):
            # echo back draft
            return {"draft_id": payload.get("draft_id"), "items": payload.get("items")}

    monkeypatch.setattr(AdapterFactory, "get_cart_order_adapter", classmethod(lambda cls: DummyAdapter()))

    items = [{"product_id": "sku-1", "qty": 2}]
    res = await service_helpers.add_cart_items("d-1", items, idempotency_key="k2")
    assert res.get("draft_id") == "d-1"
    assert isinstance(res.get("items"), list)


@pytest.mark.asyncio
async def test_checkout_cart_calls_reserve(monkeypatch):
    class DummyAdapter:
        async def reserve_items(self, payload):
            return {"reservation_id": "res-1", "status": "RESERVED"}

    monkeypatch.setattr(AdapterFactory, "get_cart_order_adapter", classmethod(lambda cls: DummyAdapter()))

    res = await service_helpers.checkout_cart("d-1", idempotency_key="k3")
    assert res.get("status") == "RESERVED"


@pytest.mark.asyncio
async def test_create_order_http_flow(monkeypatch):
    # Dummy client that behaves as aiohttp client context manager
    class DummyClient:
        def __init__(self):
            pass

        def post(self, url, json=None, headers=None):
            return AsyncCtxResp(status=201, json_data={"id": "ord-1", **(json or {})})

    class DummyAdapter:
        order_base_url = "http://order-delivery"

        async def _get_session(self):
            return DummyClient()

    monkeypatch.setattr(AdapterFactory, "get_cart_order_adapter", classmethod(lambda cls: DummyAdapter()))

    payload = {"session_id": "s1", "user_phone": "+260772000011", "business_id": "biz-1", "total_amount": 1500, "currency": "ZMW"}
    res = await service_helpers.create_order(payload, idempotency_key="ord-key")
    assert res.get("id") == "ord-1"


@pytest.mark.asyncio
async def test_initiate_order_payment_and_mark_paid(monkeypatch):
    class DummyClient:
        def post(self, url, json=None, headers=None):
            # simulate initiate_payment call
            if url.endswith("/initiate_payment"):
                return AsyncCtxResp(status=200, json_data={"status": "initiated", "external_id": "pay-1"})
            if url.endswith("/mark_paid"):
                return AsyncCtxResp(status=200, json_data={"id": "ord-1", "status": "paid"})
            return AsyncCtxResp(status=404, json_data={})

    class DummyAdapter:
        order_base_url = "http://order-delivery"

        async def _get_session(self):
            return DummyClient()

    monkeypatch.setattr(AdapterFactory, "get_cart_order_adapter", classmethod(lambda cls: DummyAdapter()))

    pay = await service_helpers.initiate_order_payment("ord-1", "+260772000011", provider="pawapay", idempotency_key="p1")
    assert pay.get("status") == "initiated"

    paid = await service_helpers.mark_order_paid("ord-1")
    assert paid.get("status") == "paid"


@pytest.mark.asyncio
async def test_confirm_delivery_calls_delivery_adapter(monkeypatch):
    class DummyClient:
        def post(self, url, json=None, headers=None):
            return AsyncCtxResp(status=200, json_data={"id": "del-1", "status": "confirmed"})

    class DummyDeliveryAdapter:
        base_url = "http://order-delivery"

        async def _get_session(self):
            return DummyClient()

    monkeypatch.setattr(AdapterFactory, "get_delivery_adapter", classmethod(lambda cls: DummyDeliveryAdapter()))

    res = await service_helpers.confirm_delivery("del-1", "123456", confirmed_by="+260772000011")
    assert res.get("status") == "confirmed" or res.get("id") == "del-1"
