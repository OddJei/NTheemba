from __future__ import annotations

import asyncio
from typing import Any, Dict

from .services.gemini_client import GeminiClient
from .models.schemas import IntentRequest


class IntentClient:
    """High-level intent client that calls Gemini and returns parsed JSON.

    This adapter uses the same strict JSON schema expected by the runtime:
    {intents:[{id,confidence,slots,hints}], next_action}
    """

    def __init__(self) -> None:
        self._gemini = GeminiClient()

    async def extract(self, request: IntentRequest, *, product_snapshot: list[dict] | None = None, max_input_tokens: int = 450, max_output_tokens: int = 80) -> Dict[str, Any]:
        """Call Gemini and parse the structured JSON output.

        Returns a dict (possibly empty) with keys `intents` and `next_action`.
        """
        payload = self._build_payload(request, product_snapshot=product_snapshot, max_input_tokens=max_input_tokens, max_output_tokens=max_output_tokens)
        try:
            raw = await self._gemini.generate_content(payload=payload, model=None)
            parsed = self._parse_response(raw)
            if isinstance(parsed, dict) and parsed:
                return parsed
            return {}
        except Exception:
            return {}

    def _build_payload(self, request: IntentRequest, *, product_snapshot: list[dict] | None = None, max_input_tokens: int = 450, max_output_tokens: int = 80) -> dict:
        # Stronger instruction: enumerate allowed canonical intent ids and require them.
        parts = []
        canonical_intents = [
            "add_item",
            "unknown",
            "view_cart",
            "confirm_order",
            "confirm_payment",
            "cancel",
            "help",
            "clear_cart",
            "remove_item",
            "track_order",
            "request_support",
        ]
        instruction = (
            "You are an intent+slot extraction service for the Custom Shopping Bot. "
            "RETURN ONLY ONE JSON OBJECT with NO MARKDOWN and NO extra text. "
            "The object MUST contain: \n  - intents: non-empty array of intents \n"
            "  - next_action: one of reply|outbound|none\n"
            "Each intent MUST be an object with keys: id (one of the canonical ids), confidence (0..1), slots (object).\n"
            "Use exactly one of the following canonical ids for each detected intent: "
            + ", ".join(canonical_intents)
            + ". If no canonical intent applies, use 'unknown'.\n"
            "Do NOT invent new intent ids, synonyms, or variations. If you cannot map an utterance to a canonical id, set id to 'unknown'.\n"
            "Return slot values exactly as simple JSON types (strings, numbers, booleans, objects)."
        )
        parts.append({"text": instruction})

        # Include a lightweight context summary
        ctx = request.context or {}
        if ctx:
            parts.append({"text": f"Context: {ctx}"})

        # If provided, include a tiny product snapshot so the model can return canonical product_ids.
        if product_snapshot:
            items = []
            for p in product_snapshot[:12]:
                pid = p.get("product_id")
                name = p.get("name")
                aliases = ",".join(p.get("aliases") or [])
                items.append(f"{pid}|{name}|{aliases}")
            parts.append({"text": "Available products (id|name|aliases):\n" + "\n".join(items)})
        user_text = (request.raw_text or "")[: max_input_tokens * 4]
        parts.append({"text": f"User: {user_text}"})
        return {"maxOutputTokens": int(max_output_tokens), "prompt": {"messages": [{"role": "user", "content": {"parts": parts}}]}}

    def _parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        # Simple JSON extractor similar to IntentService._parse_response
        try:
            candidates = raw.get("candidates") or []
            if not candidates:
                return {}
            text = ""
            try:
                text = candidates[0]["content"]["parts"][0]["text"]
            except Exception:
                text = str(candidates[0])

            # find first JSON object
            start = None
            for i, ch in enumerate(text):
                if ch in ("{", "["):
                    start = i
                    break
            if start is None:
                return {}
            import json

            try:
                return json.loads(text[start:])
            except Exception:
                return {}
        except Exception:
            return {}


client = IntentClient()
