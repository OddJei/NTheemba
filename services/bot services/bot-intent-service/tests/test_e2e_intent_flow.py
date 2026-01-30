import asyncio
import json

import pytest

from app.models.schemas import IntentRequest
from app.services.intent_service import service
from app.services.publisher import IntentPublisher


class DummyPublisher:
    def __init__(self):
        self.published = []

    async def publish_result(self, result):
        # store the serialized payload
        self.published.append(result.model_dump())


@pytest.mark.asyncio
async def test_gemini_parsed_and_published(monkeypatch):
    # Prepare a fake Gemini response returning a JSON payload in candidates
    fake_json = {
        "intents": [
            {"id": "add_item", "name": "Add Item", "confidence": 0.92, "slots": {"quantity": 2}}
        ],
        "next_action": "reply",
    }
    fake_text = json.dumps(fake_json)

    async def fake_generate_content(self, payload, model=None):
        return {"candidates": [{"content": {"parts": [{"text": fake_text}]}}]}

    # Patch GeminiClient.generate_content
    monkeypatch.setattr("app.services.gemini_client.GeminiClient.generate_content", fake_generate_content)

    # Create a minimal IntentRequest
    req = IntentRequest.model_validate({
        "event_id": "evt-test-1",
        "session_id": "sess-1",
        "raw_text": "I want 2 apples",
    })

    # Resolve using the real service (which will call our patched GeminiClient)
    result = await service.resolve(req)

    assert result is not None
    assert result.intent.id == "add_item"
    assert result.slots.get("quantity") == 2

    # Patch publisher publish_result to capture the call
    dummy = DummyPublisher()
    monkeypatch.setattr("app.services.publisher.IntentPublisher.publish_result", dummy.publish_result)

    # Call publisher with the result
    await dummy.publish_result(result)
    assert len(dummy.published) == 1
    payload = dummy.published[0]
    assert payload["event_id"] == "evt-test-1"
    assert "intents" in payload
