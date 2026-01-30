from __future__ import annotations

import asyncio
import json
from typing import Any

from ..core.config import get_settings


class GeminiClient:
    """Reply service Gemini wrapper.

    Mirrors the intent-service wrapper so the repo behaves consistently.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.endpoint = settings.gemini.endpoint
        self.default_model = settings.gemini.model
        self.api_key = (settings.gemini.api_key or "").split(",")[0].strip() if settings.gemini.api_key else None

    async def generate_content(self, payload: dict[str, Any], model: str | None = None) -> dict[str, Any]:
        model = model or self.default_model
        if isinstance(model, str) and model.startswith("models/"):
            model = model[len("models/"):]

        # Try official client first
        try:
            import genai  # type: ignore

            def call_sync() -> dict[str, Any]:
                client = genai.Client(api_key=self.api_key)
                resp = client.models.generate_content(model=model, **payload)
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
            import httpx

            url = f"{self.endpoint}/{model}:generateContent"

            # Convert from prompt.messages style to contents if needed.
            json_body = payload
            try:
                if isinstance(payload, dict) and "prompt" in payload and isinstance(payload["prompt"], dict):
                    parts_texts: list[str] = []
                    msgs = payload["prompt"].get("messages") or []
                    for m in msgs:
                        content = m.get("content") or {}
                        parts = content.get("parts") or []
                        for p in parts:
                            t = p.get("text")
                            if t:
                                parts_texts.append(t)
                    contents = [{"parts": [{"text": "\n\n".join(parts_texts)}]}] if parts_texts else payload.get("contents")
                    json_body = {"contents": contents} if contents is not None else payload
            except Exception:
                json_body = payload

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["x-goog-api-key"] = self.api_key

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers=headers, json=json_body)
                resp.raise_for_status()
                return resp.json()
