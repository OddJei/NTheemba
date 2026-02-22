import asyncio
import pytest
from unittest.mock import MagicMock
from datetime import datetime

from src.app.helpers.outbox.outbox import create_outbox_row


class DummySyncSession:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        # record call and return non-awaitable
        self.calls.append((str(sql), params))
        return None


class DummyAsyncSession:
    def __init__(self):
        self.calls = []

    async def execute(self, sql, params):
        # simulate async DB execute
        self.calls.append((str(sql), params))
        return None


@pytest.mark.asyncio
async def test_create_outbox_row_sync_session():
    s = DummySyncSession()
    await create_outbox_row(s, "test.event", {"a": 1}, correlation_id="corr-1", idempotency_key="idem-1")
    assert len(s.calls) == 1
    _, params = s.calls[0]
    assert params["event_type"] == "test.event"
    assert params["correlation_id"] == "corr-1"


@pytest.mark.asyncio
async def test_create_outbox_row_async_session():
    s = DummyAsyncSession()
    await create_outbox_row(s, "test.event", {"a": 2}, correlation_id="corr-2")
    assert len(s.calls) == 1
    _, params = s.calls[0]
    assert params["event_type"] == "test.event"
    assert params["correlation_id"] == "corr-2"
