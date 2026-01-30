import json

from app.services.intent_service import IntentService


def test_parse_response_extracts_json_from_text():
    text = (
        "Intro text...\n\n"
        "{\"intents\":[{\"id\":\"add_item\",\"name\":\"Add Item\",\"confidence\":0.95,\"slots\":{\"quantity\":2}}],\"next_action\":\"reply\"}"
        "\n\nThanks"
    )
    raw = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    parsed = IntentService._parse_response(raw)
    assert isinstance(parsed, dict)
    assert "intents" in parsed
    assert parsed["intents"][0]["id"] == "add_item"


def test_parse_response_no_json_returns_empty():
    raw = {"candidates": [{"content": {"parts": [{"text": "No JSON here"}]}}]}
    parsed = IntentService._parse_response(raw)
    assert parsed == {}
