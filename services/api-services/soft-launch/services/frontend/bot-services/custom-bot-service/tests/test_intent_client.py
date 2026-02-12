import pytest

from types import SimpleNamespace

from app.intent_client import get_intents


class DummyResp:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


@pytest.mark.asyncio
async def test_get_intents_success(monkeypatch):
    async def fake_post(self, url, json, headers):
        return DummyResp(200, {"intents": [{"id": "add_item", "slots": {"quantity": 2, "product_name": "apples"}}]})

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    intents = await get_intents(event_id="e1", session_id="s1", raw_text="2 apples", context={})
    assert isinstance(intents, list)
    assert len(intents) == 1
    assert intents[0].id == "add_item"
    assert intents[0].slots.get("quantity") == 2


@pytest.mark.asyncio
async def test_get_intents_non_200_returns_empty(monkeypatch):
    async def fake_post(self, url, json, headers):
        return DummyResp(500, {})

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    intents = await get_intents(event_id="e2", session_id="s2", raw_text="hello", context={})
    assert intents == []


@pytest.mark.asyncio
async def test_get_intents_exception_retries_then_empty(monkeypatch):
    async def fake_post(self, url, json, headers):
        raise Exception("network")

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    intents = await get_intents(event_id="e3", session_id="s3", raw_text="hello", context={})
    assert intents == []
