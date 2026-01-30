from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure `app` package is importable when running pytest from the service folder.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models.schemas import IntentRequest

from app.intent_client import client as intent_client


@pytest.mark.asyncio
async def test_extract_parses_json(monkeypatch):
    async def fake_generate_content(payload=None, model=None):
        return {
            "candidates": [
                {
                    "content": {"parts": [{"text": '{"intents":[{"id":"add_item","confidence":0.95,"slots":{"quantity":2}}],"next_action":"reply"}'}]}
                }
            ]
        }

    # Patch the GeminiClient.generate_content used by intent_client
    from app.services.gemini_client import GeminiClient

    monkeypatch.setattr(GeminiClient, "generate_content", staticmethod(fake_generate_content))

    req = IntentRequest(
        event_id="evt_test",
        session_id="sess_test",
        raw_text="Buy two apples",
    )

    parsed = await intent_client.extract(req)
    assert isinstance(parsed, dict)
    assert parsed.get("intents") or parsed.get("intent") or parsed.get("next_action")
    intents = parsed.get("intents")
    assert isinstance(intents, list)
    assert intents[0]["id"] == "add_item"
    assert intents[0]["slots"]["quantity"] == 2


@pytest.mark.asyncio
async def test_extract_handles_unparseable(monkeypatch):
    async def fake_generate_content(payload=None, model=None):
        return {"candidates": [{"content": {"parts": [{"text": "I won't return JSON"}]}}]}

    from app.services.gemini_client import GeminiClient

    monkeypatch.setattr(GeminiClient, "generate_content", staticmethod(fake_generate_content))

    req = IntentRequest(event_id="evt2", session_id="sess2", raw_text="nonsense")
    parsed = await intent_client.extract(req)
    assert parsed == {}
