"""Gemini HTTP adapter for advisory intent and reply-style proposals."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx

from ntheemba.config import Settings

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiResponseError(RuntimeError):
    """Raised when Gemini returns an unusable response."""


class GeminiClient:
    """Small REST client for Gemini JSON-only proposals.

    The API key is passed only as an HTTP query parameter and is never exposed
    through prompts, response objects, or exception messages raised here.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        retry_count: int,
        max_output_tokens: int,
        client: httpx.AsyncClient | None = None,
        base_url: str = _GEMINI_BASE_URL,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key must not be empty")
        if not model.strip():
            raise ValueError("model must not be empty")
        self._api_key = api_key
        self._model = model.strip().removeprefix("models/")
        self._timeout_seconds = timeout_seconds
        self._retry_count = retry_count
        self._max_output_tokens = max_output_tokens
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def generate_json(
        self,
        *,
        instruction: str,
        payload: Mapping[str, Any],
        max_output_tokens: int | None = None,
    ) -> Mapping[str, Any]:
        """Request one JSON object from Gemini and parse the first text part."""

        if not instruction.strip():
            raise ValueError("instruction must not be empty")
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                instruction.strip()
                                + "\n\nInput JSON:\n"
                                + json.dumps(payload, sort_keys=True, separators=(",", ":"))
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": max_output_tokens or self._max_output_tokens,
                "responseMimeType": "application/json",
            },
        }
        response = await self._post(body)
        return self._parse_response(response)

    async def _post(self, body: Mapping[str, Any]) -> httpx.Response:
        endpoint = f"{self._base_url}/models/{self._model}:generateContent"
        attempts = self._retry_count + 1
        last_error: Exception | None = None
        for _attempt in range(attempts):
            try:
                if self._client is not None:
                    response = await self._client.post(
                        endpoint,
                        params={"key": self._api_key},
                        json=body,
                        timeout=self._timeout_seconds,
                    )
                else:
                    async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                        response = await client.post(
                            endpoint,
                            params={"key": self._api_key},
                            json=body,
                        )
                if response.status_code < 500:
                    return response
                last_error = GeminiResponseError("Gemini returned a transient error")
            except httpx.HTTPError as error:
                last_error = error
        raise GeminiResponseError("Gemini request failed") from last_error

    @staticmethod
    def _parse_response(response: httpx.Response) -> Mapping[str, Any]:
        if response.status_code >= 400:
            raise GeminiResponseError("Gemini rejected the request")
        try:
            envelope = response.json()
        except ValueError as error:
            raise GeminiResponseError("Gemini returned a non-JSON response") from error
        candidates = envelope.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise GeminiResponseError("Gemini response did not include a candidate")
        content = candidates[0].get("content")
        parts = content.get("parts") if isinstance(content, Mapping) else None
        if not isinstance(parts, list) or not parts:
            raise GeminiResponseError("Gemini candidate did not include text")
        text = parts[0].get("text") if isinstance(parts[0], Mapping) else None
        if not isinstance(text, str) or not text.strip():
            raise GeminiResponseError("Gemini candidate text is empty")
        return _parse_json_object(text)


class GeminiIntentProvider:
    """Gemini-backed implementation of the interpretation model protocol."""

    def __init__(self, client: GeminiClient) -> None:
        self._client = client

    async def propose(
        self,
        text: str,
        context: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Return one untrusted intent proposal for strict local validation."""

        instruction = """
You are Ntheemba's advisory intent recognizer.
Return exactly one JSON object with keys: intent, role, confidence, entities,
and reasoning_code. Choose intent only from allowed_actions in the input.
Do not assert external business facts such as price, stock, availability,
request IDs, payment status, policies, internal IDs, or shop selection.
Use entities only for customer-supplied text, quantities, dates, contact
details, fulfilment method, selection, barcode, or search query.
"""
        return await self._client.generate_json(
            instruction=instruction,
            payload={"text": text, "context": dict(context)},
            max_output_tokens=384,
        )


class GeminiReplyTextProvider:
    """Gemini-backed text proposal for already-approved replies."""

    def __init__(self, client: GeminiClient) -> None:
        self._client = client

    async def propose_text(
        self,
        *,
        text: str,
        response_type: str,
        blend: float,
        languages: tuple[str, ...],
        protected_terms: tuple[str, ...],
    ) -> str:
        """Return one style-only localized text candidate."""

        instruction = """
You are Ntheemba's reply style assistant.
Rewrite the approved customer reply into friendly Zambian English with a light
local-language blend. Use only the languages named in input. Keep the local
language share near the requested blend. Do not add facts, promises, discounts,
stock claims, payment claims, policy statements, business hours, or delivery
promises. Preserve every protected term exactly. Return JSON only:
{"text":"rewritten reply"}.
"""
        proposal = await self._client.generate_json(
            instruction=instruction,
            payload={
                "text": text,
                "response_type": response_type,
                "local_language_blend": blend,
                "local_language_variants": languages,
                "protected_terms": protected_terms,
            },
        )
        value = proposal.get("text")
        if not isinstance(value, str):
            raise GeminiResponseError("Gemini reply proposal is missing text")
        return value


def build_gemini_client_from_settings(settings: Settings) -> GeminiClient | None:
    """Build the Gemini client only when the opt-in runtime flag is enabled."""

    if not settings.gemini_enabled:
        return None
    if settings.gemini_api_key is None:
        raise ValueError("gemini_api_key is required when gemini_enabled")
    return GeminiClient(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        timeout_seconds=settings.gemini_timeout_seconds,
        retry_count=settings.gemini_retry_count,
        max_output_tokens=settings.gemini_max_output_tokens,
    )


def _parse_json_object(text: str) -> Mapping[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise GeminiResponseError("Gemini text was not a JSON object") from error
    if not isinstance(parsed, Mapping):
        raise GeminiResponseError("Gemini text was not a JSON object")
    return parsed
