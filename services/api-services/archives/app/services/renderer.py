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


def _build_chat_stage_fallback_text(req: ReplyRequest, settings: Settings) -> str:
    tv = req.template_vars or {}
    bot_name = tv.get("bot_name") or settings.identity.persona_name
    business_name = tv.get("business_name") or _business_name(req, settings)

    base = (req.text or "").strip()
    if not base:
        base = f"Hi — I'm {bot_name} from {business_name}."

    suggestions = tv.get("product_suggestions") if isinstance(tv, dict) else None
    names: list[str] = []
    if isinstance(suggestions, list):
        for it in suggestions[:3]:
            if not isinstance(it, dict):
                continue
            name = it.get("name") or it.get("title") or it.get("product_name")
            if name:
                names.append(str(name))

    if names:
        base = f"{base} I suggest: {', '.join(names)}."

    ctas = tv.get("cta_labels") if isinstance(tv, dict) else None
    if not (isinstance(ctas, list) and ctas):
        play_label = f"Play with {names[0]}" if names else "Play with a product"
        ctas = [play_label, "Explore offers", "Help"]

    ctas_text = " | ".join([str(x) for x in ctas if x])
    if ctas_text:
        base = f"{base} Reply with: {ctas_text}."

    return base


def _chat_stage_gemini_payload(draft: str, req: ReplyRequest, settings: Settings) -> dict[str, Any]:
    tv = req.template_vars or {}
    ctas = tv.get("cta_labels") if isinstance(tv, dict) else []
    if not (isinstance(ctas, list) and ctas):
        ctas = ["Play with a product", "Explore offers", "Help"]

    instruction = (
        "You are a reply-writing service for a commerce chat bot. "
        "You MUST return ONLY one JSON object with a single key 'text'. "
        "No markdown, no extra words. "
        "Keep it short, friendly, and safe. "
        "Keep the CTA labels EXACTLY as provided and include them in the reply. "
        "Do not ask the user to choose a payment provider (MTN/Airtel). "
        "If payment details are needed, ask only for the mobile number."
    )

    parts = [
        {"text": instruction},
        {"text": f"Persona name: {settings.identity.persona_name}"},
        {"text": f"Business name: {_business_name(req, settings)}"},
        {"text": f"Stage: {tv.get('stage') or 'chat'}"},
        {"text": f"Sub-stage: {tv.get('sub_stage') or 'greeting'}"},
        {"text": f"CTA labels (must appear verbatim): {', '.join([str(x) for x in ctas])}"},
        {"text": f"Draft reply to improve (keep meaning): {draft}"},
    ]

    return {
        "maxOutputTokens": int(settings.gemini.max_output_tokens),
        "prompt": {"messages": [{"role": "user", "content": {"parts": parts}}]},
    }


class ReplyRenderer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._gemini = GeminiClient()

    async def render_text(self, req: ReplyRequest) -> str:
        # Chat-stage NLG path
        if req.render_type == "nlg" and req.template_id == "chat.stage.reply":
            draft = _build_chat_stage_fallback_text(req, self._settings)

            if not self._settings.gemini.enabled:
                return self._ensure_warmth_and_local_phrases(draft)

            payload = _chat_stage_gemini_payload(draft, req, self._settings)
            try:
                raw = await self._gemini.generate_content(payload=payload, model=None)
                improved = _extract_gemini_text(raw)
                final = improved or draft
            except Exception:
                final = draft

            return self._ensure_warmth_and_local_phrases(final)

        # Default path
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
