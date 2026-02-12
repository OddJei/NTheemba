from __future__ import annotations

import asyncio
import json
from typing import Any

from ..core.config import get_settings


class GeminiClient:
    """Simple wrapper to call Gemini / Generative Language APIs.

    Attempts to use the official `genai` client if available, otherwise falls
    back to an HTTP call using `httpx`.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.endpoint = settings.gemini.endpoint
        self.default_model = settings.gemini.model
        self.api_key = (settings.gemini.api_key or "").split(",")[0].strip() if settings.gemini.api_key else None

    async def generate_content(self, payload: dict[str, Any], model: str | None = None) -> dict[str, Any]:
        """Generate content using the configured model.

        `payload` should be structured according to the `generateContent` API
        (e.g. {"prompt": {"messages": [...]}, "maxOutputTokens": ...}).
        """
        model = model or self.default_model
        # Normalize model: accept either 'gemini-3-flash-preview' or 'models/gemini-3-flash-preview'
        if isinstance(model, str) and model.startswith("models/"):
            model = model[len("models/"):]

        # Try official genai client if available (sync) by running in threadpool.
        try:
            import genai  # type: ignore

            def call_sync() -> dict[str, Any]:
                client = genai.Client(api_key=self.api_key)
                # The official client may return a rich object; convert to dict.
                resp = client.models.generate_content(model=model, **payload)
                # resp may be a dict-like or object with .to_dict(); attempt both.
                try:
                    return dict(resp)
                except Exception:
                    try:
                        return resp.to_dict()
                    except Exception:
                        return json.loads(json.dumps(resp, default=str))

            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, call_sync)
        except Exception:
            # Fallback to httpx async call
            import httpx

            url = f"{self.endpoint}/{model}:generateContent"
            import httpx

            # Some Gemini models (Generative Language API) expect a `contents` shape
            # with parts: [{"parts": [{"text": "..."}]}] and an API key in the
            # `x-goog-api-key` header. Convert from our `prompt.messages` shape when
            # present.
            json_body = payload
            try:
                if isinstance(payload, dict) and "prompt" in payload and isinstance(payload["prompt"], dict):
                    # Extract parts text from prompt.messages -> prompt.messages[*].content.parts
                    parts_texts: list[str] = []
                    msgs = payload["prompt"].get("messages") or []
                    for m in msgs:
                        content = m.get("content") or {}
                        parts = content.get("parts") or []
                        for p in parts:
                            t = p.get("text") or p.get("text", "")
                            if t:
                                parts_texts.append(t)
                    # Fallback: if no messages parts, try top-level 'parts' in payload
                    if not parts_texts and "parts" in payload:
                        for p in payload.get("parts") or []:
                            if isinstance(p, dict) and p.get("text"):
                                parts_texts.append(p.get("text"))

                    # Compose contents structure
                    contents = [{"parts": [{"text": "\n\n".join(parts_texts)}]}] if parts_texts else payload.get("contents")
                    json_body = {"contents": contents} if contents is not None else payload

            except Exception:
                json_body = payload

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                # Use Google-style header when calling generativelanguage.googleapis.com
                headers["x-goog-api-key"] = self.api_key

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers=headers, json=json_body)
                resp.raise_for_status()
                return resp.json()
