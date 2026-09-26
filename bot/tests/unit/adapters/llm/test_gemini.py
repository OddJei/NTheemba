"""Tests for the Gemini advisory model adapter."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx
import pytest
from ntheemba.adapters.llm import GeminiClient, GeminiIntentProvider, GeminiResponseError


def _response(payload: Mapping[str, Any], status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload)


def _candidate(text: str) -> Mapping[str, Any]:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": text,
                        }
                    ]
                }
            }
        ]
    }


@pytest.mark.asyncio
async def test_gemini_intent_provider_posts_safe_json_prompt_without_key() -> None:
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content.decode())
        return _response(
            _candidate(
                json.dumps(
                    {
                        "intent": "catalogue_search",
                        "role": "new_request",
                        "confidence": 0.87,
                        "entities": {"query": "anjoy"},
                    }
                )
            )
        )

    client = GeminiClient(
        api_key="secret-gemini-key",
        model="gemini-test",
        timeout_seconds=1,
        retry_count=0,
        max_output_tokens=128,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        base_url="https://gemini.test/v1beta",
    )
    provider = GeminiIntentProvider(client)

    proposal = await provider.propose(
        "Do you have Anjoy?",
        {"allowed_actions": ["catalogue_search"], "enabled_capabilities": ["product.catalogue"]},
    )

    assert proposal["intent"] == "catalogue_search"
    assert "key=secret-gemini-key" in seen["url"]
    body_text = seen["body"]["contents"][0]["parts"][0]["text"]
    assert "secret-gemini-key" not in body_text
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.asyncio
async def test_gemini_client_rejects_malformed_json_candidate() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return _response(_candidate("not json"))

    client = GeminiClient(
        api_key="secret",
        model="gemini-test",
        timeout_seconds=1,
        retry_count=0,
        max_output_tokens=128,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        base_url="https://gemini.test/v1beta",
    )

    with pytest.raises(GeminiResponseError, match="JSON object"):
        await client.generate_json(instruction="Return JSON", payload={"text": "hello"})


@pytest.mark.asyncio
async def test_gemini_client_rejects_http_error_without_leaking_body() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "secret remote detail"}})

    client = GeminiClient(
        api_key="secret",
        model="gemini-test",
        timeout_seconds=1,
        retry_count=0,
        max_output_tokens=128,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        base_url="https://gemini.test/v1beta",
    )

    with pytest.raises(GeminiResponseError) as caught:
        await client.generate_json(instruction="Return JSON", payload={"text": "hello"})

    assert "secret remote detail" not in str(caught.value)
