import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

# Ensure service package importable
SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

from app.helpers import service_helpers


class DummyResp:
    def __init__(self):
        self.status = 200

    async def text(self):
        return "ok"

    async def json(self):
        return {"ok": True}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummySession:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, *a, **k):
        return DummyResp()


@pytest.mark.asyncio
async def test_send_notification_receipt_direct(monkeypatch):
    # Patch aiohttp.ClientSession to avoid real network
    import aiohttp

    monkeypatch.setattr(aiohttp, "ClientSession", DummySession)

    res = await service_helpers.send_notification_receipt(
        None, request_id="r1", status="delivered", reliable=False
    )

    assert res.get("status") == "posted"
import pytest

from app.adapters.factory import AdapterFactory
from app.helpers import service_helpers


class AsyncResp:
    def __init__(self, status, json_data=None, text_data=""):
        self.status_code = status
        self._json = json_data
        self._text = text_data

    def json(self):
        return self._json

    def text(self):
        return self._text


@pytest.mark.asyncio
async def test_create_bot_success(monkeypatch):
    class DummyClient:
        async def post(self, url, json):
            return AsyncResp(201, {"id": "bot1", "phone": json.get("phone")})

    class DummyAdapter:
        base_url = "http://bot-session"

        async def _get_client(self):
            return DummyClient()

    monkeypatch.setattr(AdapterFactory, "get_bot_session_adapter", classmethod(lambda cls: DummyAdapter()))

    res = await service_helpers.create_bot("+260772000000", name="ICE Bot")
    assert res.get("id") == "bot1"


@pytest.mark.asyncio
async def test_get_bot_by_phone_not_found(monkeypatch):
    class DummyClient:
        async def get(self, url):
            return AsyncResp(404, None, "not found")

    class DummyAdapter:
        base_url = "http://bot-session"

        async def _get_client(self):
            return DummyClient()

    monkeypatch.setattr(AdapterFactory, "get_bot_session_adapter", classmethod(lambda cls: DummyAdapter()))

    res = await service_helpers.get_bot_by_phone("+260000000")
    assert res == {}


@pytest.mark.asyncio
async def test_create_user_bot_session(monkeypatch):
    class DummyClient:
        async def post(self, url, json, headers=None):
            return AsyncResp(201, {"session_id": "sess-1", "user_phone": json.get("user_phone")})

    class DummyAdapter:
        base_url = "http://bot-session"

        async def _get_client(self):
            return DummyClient()

    monkeypatch.setattr(AdapterFactory, "get_user_bot_session_adapter", classmethod(lambda cls: DummyAdapter()))

    session = await service_helpers.create_user_bot_session("+260772000000", "biz-1", {"platform": "whatsapp"})
    assert session.get("session_id") == "sess-1"


@pytest.mark.asyncio
async def test_create_session_state_and_upgrade_cycle(monkeypatch):
    class DummyClient:
        async def post(self, url, json):
            if url.endswith("/state"):
                return AsyncResp(200, None, "ok")
            if url.endswith("/cycles"):
                return AsyncResp(201, {"id": "cycle-1", "state": json.get("state")}, "created")

    class DummyAdapter:
        base_url = "http://bot-session"

        async def _get_client(self):
            return DummyClient()

    monkeypatch.setattr(AdapterFactory, "get_user_bot_session_adapter", classmethod(lambda cls: DummyAdapter()))

    ok = await service_helpers.create_session_state("sess-1", "cart", {"cart_items": []})
    assert ok is True

    cycle = await service_helpers.upgrade_cycle_state("sess-1", "order", metadata={"from": "cart"})
    assert cycle.get("id") == "cycle-1"


@pytest.mark.asyncio
async def test_close_user_bot_session(monkeypatch):
    class DummyClient:
        async def post(self, url, headers=None):
            return AsyncResp(200, None, "ok")

    class DummyAdapter:
        base_url = "http://bot-session"

        async def _get_client(self):
            return DummyClient()

    monkeypatch.setattr(AdapterFactory, "get_user_bot_session_adapter", classmethod(lambda cls: DummyAdapter()))

    closed = await service_helpers.close_user_bot_session("sess-1", reason="order_complete")
    assert closed is True
