import asyncio
import json
import pytest

import httpx
import os
from app.utils.audit import log_event
from app.config.settings import settings


@pytest.mark.asyncio
async def test_log_event_posts(monkeypatch):
    called = {}

    async def fake_post(self, url, json=None, **kwargs):
        called['url'] = url
        called['json'] = json

        class Resp:
            status_code = 200

            def raise_for_status(self):
                return None

        return Resp()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    # ensure auditing enabled via env override
    monkeypatch.setenv("AUDIT_ENABLED", "1")

    await log_event("notification-service", "test_event", "user:1", "notification", "n1", {"k": "v"})

    assert 'url' in called
    assert called['json']['service'] == 'notification-service'


@pytest.mark.asyncio
async def test_log_event_skipped_when_disabled(monkeypatch):
    # if auditing is disabled, httpx.AsyncClient.post must NOT be called
    async def fail_post(self, url, json=None, **kwargs):
        raise AssertionError("httpx.post should not be called when AUDIT_ENABLED is False")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail_post)
    monkeypatch.setenv("AUDIT_ENABLED", "0")

    # Should not raise
    await log_event("notification-service", "test_event", "user:1", "notification", "n1", {"k": "v"})
