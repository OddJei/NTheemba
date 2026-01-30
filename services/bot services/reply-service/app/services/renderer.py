from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ..core.config import Settings
from ..models import ReplyRequest
from .gemini_client import GeminiClient
from ..prompts.phrase_bank import BEMBA_NYANJA_PHRASES
from typing import List


def _business_name(req: ReplyRequest, settings: Settings) -> str:
    try:
        bn = (req.meta or {}).get("business_name")
        if isinstance(bn, str) and bn.strip():
            return bn.strip()
    except Exception:
        pass
    return settings.identity.business_name_default


def _prefix(req: ReplyRequest, settings: Settings) -> str:
    persona = settings.identity.persona_name
    style = (settings.identity.prefix_style or "persona_at_business").strip().lower()

    if style == "none":
        return ""
    if style == "persona_only":
        return f"{persona}: "

    # persona_at_business
    bn = _business_name(req, settings)
    return f"{persona} at {bn}: "


def _extract_gemini_text(raw: dict[str, Any]) -> Optional[str]:
    # Try official candidates shape first
    try:
        candidates = raw.get("candidates") or []
        if not candidates:
            return None
        text = candidates[0]["content"]["parts"][0]["text"]
    except Exception:
        text = None

    if not text:
        # fallback
        text = json.dumps(raw, default=str)

    # Find first JSON object and parse
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            start = i
            break
    if start is None:
        return None

    try:
        obj = json.loads(text[start:])
        if isinstance(obj, dict) and isinstance(obj.get("text"), str):
            return obj["text"].strip()
    except Exception:
        return None

    return None


class ReplyRenderer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._gemini = GeminiClient()

    async def render_text(self, req: ReplyRequest) -> str:
        base_text = (req.text or "").strip()
        if not base_text:
            # Fallback generic
            base_text = "Sorry, I couldn't process that message. Please try again."

        # Always apply persona prefix (configurable)
        initial = _prefix(req, self._settings) + base_text

        # Optional Gemini polish
        if not self._settings.gemini.enabled:
            # Ensure warmth + local phrases even without Gemini
            return self._ensure_warmth_and_local_phrases(initial)

        instruction = (
            "You are a reply-writing service. "
            "You MUST return ONLY one JSON object with a single key 'text'. "
            "No markdown, no extra words. "
            "Keep it short, friendly, and safe. "
            "Do not ask the user to choose a payment provider (MTN/Airtel). "
            "If payment details are needed, ask only for the mobile number."
        )

        persona = self._settings.identity.persona_name
        bn = _business_name(req, self._settings)

        parts = [
            {"text": instruction},
            {"text": f"Persona name: {persona}"},
            {"text": f"Business name: {bn}"},
            {"text": f"Draft reply to improve (keep meaning): {initial}"},
        ]

        payload = {
            "maxOutputTokens": int(self._settings.gemini.max_output_tokens),
            "prompt": {"messages": [{"role": "user", "content": {"parts": parts}}]},
        }

        try:
            raw = await self._gemini.generate_content(payload=payload, model=None)
            improved = _extract_gemini_text(raw)
            final = improved or initial
        except Exception:
            final = initial

        # Post-process to ensure warm persona + ~10% local phrases
        return self._ensure_warmth_and_local_phrases(final)

    def _ensure_warmth_and_local_phrases(self, text: str) -> str:
        """Ensure the reply sounds warm and inject ~10% local phrases from the phrase bank.

        Deterministic insertion: split into sentences and insert phrases spaced evenly to reach
        approx 10% insertion rate (at least 1 for multi-sentence texts).
        """
        try:
            s = text.strip()
            if not s:
                return s

            # Simple sentence splitter on punctuation. Keep delimiters.
            import re

            parts = re.split(r'(?<=[.!?])\s+', s)
            if len(parts) <= 1:
                # Single sentence -> append a short friendly phrase (~10% means at least one for short replies)
                phrase = BEMBA_NYANJA_PHRASES[0]
                if phrase in s:
                    return s
                return f"{s} {phrase}"

            n = len(parts)
            # target number of inserts (10% rounding)
            target = max(1, round(n * 0.10))

            # choose phrases deterministically by cycling the bank
            inserts: List[str] = []
            for i in range(target):
                inserts.append(BEMBA_NYANJA_PHRASES[i % len(BEMBA_NYANJA_PHRASES)])

            # Spacing interval to distribute inserts
            interval = max(1, n // target)

            new_parts: List[str] = []
            insert_idx = 0
            for idx, sentence in enumerate(parts):
                sentence = sentence.strip()
                new_parts.append(sentence)
                # Insert after this sentence if it's the correct interval
                if (idx + 1) % interval == 0 and insert_idx < len(inserts):
                    phrase = inserts[insert_idx]
                    # Avoid duplicate phrase already present
                    if phrase not in sentence:
                        new_parts.append(phrase)
                    insert_idx += 1

            # Join with a space
            return ' '.join(new_parts)
        except Exception:
            return text
