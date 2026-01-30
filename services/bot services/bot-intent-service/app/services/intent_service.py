from __future__ import annotations

import json
import re
import time
from typing import Any, Iterable

import httpx

from ..core.config import get_settings
from ..models.schemas import Attachment, IntentInfo, IntentRequest, IntentResponse, DetectedIntent
from .summarizer import summarize_context
from ..intent_client import client as intent_client
from .gemini_client import GeminiClient
from .product_lookup import lookup_products_from_request


class AttachmentLimitError(ValueError):
    """Raised when attachments exceed configured size budgets."""


class IntentService:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        settings = get_settings()
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=settings.gemini.timeout_seconds)
        return self._client

    @staticmethod
    def _validate_attachments(attachments: Iterable[Attachment]) -> None:
        settings = get_settings()
        total = 0
        for attachment in attachments:
            total += attachment.size
            if attachment.size > settings.attachment_hard_limit:
                raise AttachmentLimitError(
                    f"Attachment {attachment.name} exceeds hard limit of {settings.attachment_hard_limit} chars"
                )
        if total > settings.attachment_hard_limit:
            raise AttachmentLimitError(
                f"Combined attachment size {total} exceeds hard limit of {settings.attachment_hard_limit} chars"
            )

    @staticmethod
    def _deterministic_resolve(request: IntentRequest) -> tuple[IntentInfo, dict[str, Any], str, dict[str, Any]]:
        """Minimal deterministic intent resolver.

        This is intentionally simple and safe: it provides baseline intent classification
        + a few slots using regex/keywords. It should be replaced by a proper classifier/LLM later.
        """

        text = (request.raw_text or "").strip().lower()
        slots: dict[str, Any] = {}
        diagnostics: dict[str, Any] = {"fallback": "deterministic", "model_id": "deterministic-v1"}

        # Quantity like "2" or "x2" or "2x"
        qty_match = re.search(r"\b(x\s*)?(\d{1,3})\b", text)
        if qty_match:
            try:
                slots["quantity"] = int(qty_match.group(2))
            except Exception:
                pass

        # Simple price/budget slot
        money_match = re.search(r"\b(r|zar|ksh|kes|usd|\$)\s*(\d+(?:\.\d+)?)\b", text)
        if money_match:
            slots["budget"] = money_match.group(0)

        # Very lightweight intent mapping (aligned to custom-bot-service canonical ids)
        if text.upper() in {"CONFIRM ORDER"}:
            intent = IntentInfo(id="confirm_order", name=None, confidence=0.99)
            next_action = "reply"
        elif text.upper() in {"CONFIRM PAYMENT"}:
            intent = IntentInfo(id="confirm_payment", name=None, confidence=0.99)
            next_action = "reply"
        elif any(k in text for k in ["cancel", "stop", "abort"]):
            intent = IntentInfo(id="cancel", name=None, confidence=0.85)
            next_action = "reply"
        elif any(k in text for k in ["help", "how do i", "what can you do"]):
            intent = IntentInfo(id="help", name=None, confidence=0.80)
            next_action = "reply"
        elif any(k in text for k in ["view cart", "show cart", "my cart"]):
            intent = IntentInfo(id="view_cart", name=None, confidence=0.78)
            next_action = "reply"
        elif any(k in text for k in ["clear cart", "empty cart"]):
            intent = IntentInfo(id="clear_cart", name=None, confidence=0.78)
            next_action = "reply"
        elif any(k in text for k in ["remove"]):
            intent = IntentInfo(id="remove_item", name=None, confidence=0.70)
            next_action = "reply"
        elif any(k in text for k in ["buy", "purchase", "i want", "add", "get me"]):
            intent = IntentInfo(id="add_item", name=None, confidence=0.72)
            next_action = "reply"
        else:
            intent = IntentInfo(id="fallback_unknown_intent", name=None, confidence=0.40)
            next_action = "reply"

        return intent, slots, next_action, diagnostics

    async def resolve(self, request: IntentRequest) -> IntentResponse:
        settings = get_settings()
        attachments = request.attachments or []
        self._validate_attachments(attachments)

        started = time.perf_counter()
        intents_list = []

        # Prefer Gemini when enabled; fall back to deterministic resolver on errors or empty parse.
        intent = None
        slots = {}
        next_action = "reply"
        diagnostics = {"fallback": "deterministic", "model_id": "deterministic-v1"}

        if settings.gemini.enabled and settings.gemini.api_key:
            try:
                api_key = (settings.gemini.api_key or "").split(",")[0].strip()
                if not api_key:
                    raise ValueError("Gemini enabled but no API key present")

                diagnostics["gemini_attempted"] = True
                # Pre-search for a small product snapshot and include it in the prompt.
                try:
                    snapshot = await lookup_products_from_request(request)
                except Exception:
                    snapshot = []

                # Use the high-level IntentClient adapter which returns parsed JSON.
                parsed = await intent_client.extract(request, product_snapshot=snapshot, max_input_tokens=settings.gemini.max_input_tokens, max_output_tokens=settings.gemini.max_output_tokens)

                if isinstance(parsed, dict) and parsed:
                    # Gemini produced structured output. Use it as primary result.
                    parsed_intents = parsed.get("intents") or parsed.get("intent")
                    if isinstance(parsed_intents, list) and parsed_intents:
                        diagnostics["multi_intents"] = parsed_intents
                        for pi in parsed_intents:
                            if isinstance(pi, dict) and pi.get("id"):
                                intents_list.append(DetectedIntent(
                                    id=str(pi.get("id")),
                                    slots=pi.get("slots") or {},
                                    confidence=float(pi.get("confidence", 1.0))
                                ))

                        first = parsed_intents[0]
                        if isinstance(first, dict) and first.get("id"):
                            intent = IntentInfo(
                                id=str(first.get("id")),
                                name=first.get("name"),
                                confidence=float(first.get("confidence", 1.0)),
                            )
                            slots = first.get("slots") or {}
                            if parsed.get("next_action") in {"reply", "outbound", "none"}:
                                next_action = parsed["next_action"]
                    else:
                        parsed_intent = parsed.get("intent")
                        if isinstance(parsed_intent, dict) and parsed_intent.get("id"):
                            intent = IntentInfo(
                                id=str(parsed_intent.get("id")),
                                name=parsed_intent.get("name"),
                                confidence=float(parsed_intent.get("confidence", 1.0)),
                            )
                        elif isinstance(parsed_intent, str):
                            intent = IntentInfo(id=parsed_intent, confidence=float(parsed.get("confidence", 1.0)))

                        parsed_slots = parsed.get("slots") or parsed.get("entities")
                        if isinstance(parsed_slots, dict):
                            slots = parsed_slots

                        if parsed.get("next_action") in {"reply", "outbound", "none"}:
                            next_action = parsed["next_action"]

                    diagnostics.update({"model_id": settings.gemini.model, "fallback": "gemini"})
                    # If Gemini returned product_ids in slots, suggest required blobs for resolver hydration.
                    try:
                        required = []
                        for pi in parsed_intents:
                            if isinstance(pi, dict):
                                slots = pi.get("slots") or {}
                                pid = slots.get("product_id") or slots.get("product")
                                if pid:
                                    required.append(f"product:{pid}")
                        if required:
                            diagnostics["required_blobs"] = required
                    except Exception:
                        pass
                else:
                    diagnostics["gemini_parse"] = "empty_or_unparseable"
                    intent, slots, next_action, det_diag = self._deterministic_resolve(request)
                    diagnostics.update(det_diag)
            except Exception as exc:
                diagnostics.update({"gemini_error": str(exc), "fallback": "deterministic"})
                intent, slots, next_action, det_diag = self._deterministic_resolve(request)
                diagnostics.update(det_diag)
        else:
            # Gemini not enabled -> deterministic primary.
            intent, slots, next_action, diagnostics = self._deterministic_resolve(request)

        latency_ms = int((time.perf_counter() - started) * 1000)
        diagnostics.setdefault("latency_ms", latency_ms)

        # Ensure we always have a valid IntentInfo for validation (fallback deterministic if needed)
        if intent is None:
            intent, slots, next_action, det_diag = self._deterministic_resolve(request)
            diagnostics.update(det_diag)

        # Normalize fallback intent ids to legacy 'unknown' for test compatibility
        try:
            if intent and getattr(intent, "id", "").startswith("fallback"):
                intent = IntentInfo(id="unknown", name=intent.name, confidence=intent.confidence)
        except Exception:
            pass

        # Do not apply heuristic LLM id normalizations here. The Gemini prompt enforces canonical ids.

        return IntentResponse(
            event_id=request.event_id,
            session_id=request.session_id,
            intent=intent,
            slots=slots,
            intents=intents_list,
            intent_required=bool(request.enriched_meta.get("intent_required", True)) if request.enriched_meta else True,
            next_action=next_action,  # type: ignore[arg-type]
            diagnostics=diagnostics,
            raw_input=request.raw_text,
        )

    @staticmethod
    def _build_payload(request: IntentRequest, max_input_tokens: int = 450, max_output_tokens: int = 50) -> dict:
        parts = []
        # Instruction: force strict JSON output so parsing is reliable.
        instruction = (
            "You are an intent+slot extraction service for the Custom Shopping Bot. "
            "RETURN ONLY ONE JSON OBJECT with NO MARKDOWN and NO extra text. "
            "The object MUST contain: intents (non-empty array) and next_action. "
            "Each intent MUST be: {id: string, confidence: number 0..1, slots: object, hints?: object}. "
            "Use canonical intent ids and slot keys from the provided context. If unknown, use null. "
            "next_action must be one of: reply|outbound|none.\n\n"
            "Example (shape only):\n{" + '"intents": [{"id":"add_item","confidence":0.95,"slots":{}}],"next_action":"reply"}'
        )
        parts.append({"text": instruction})

        # Inject canonical mapping / slot schema (kept concise)
        parts.append({"text": "Canonical spec: docs/custom_bot_gemini_context.md"})

        # Summarize context from request meta/attachments
        context_str = summarize_context(request)
        if context_str:
             parts.append({"text": f"Context:\n{context_str}"})

        # We'll respect configured token limits by truncating the raw_text and attachments.
        max_input_chars = int((max_input_tokens or 450) * 4)

        user_text = request.raw_text or ""
        if len(user_text) > max_input_chars:
            user_text = user_text[: max_input_chars - 3] + "..."
        parts.append({"text": f"User: {user_text}"})
        # attachments - convert to inline content
        remaining = max_input_chars - sum(len(p.get("text", "")) for p in parts)
        for attachment in request.attachments:
            content = attachment.content or ""
            if len(content) > remaining:
                content = content[: max(0, remaining - 3)] + "..."
            if not content:
                continue
            parts.append({"text": f"[{attachment.name}]\n{content}"})
            remaining = max_input_chars - sum(len(p.get("text", "")) for p in parts)
            if remaining <= 0:
                break

        # Compose Gemini request payload with a maxOutputTokens hint.
        payload = {
            "maxOutputTokens": int(max_output_tokens or 50),
            "prompt": {"messages": [{"role": "user", "content": {"parts": parts}}]},
        }
        return payload

    @staticmethod
    def _parse_response(raw: dict) -> dict:
        def _extract_json_from_text(s: str):
            if not s or not isinstance(s, str):
                return None
            # find first JSON object/array start
            start = None
            for i, ch in enumerate(s):
                if ch in ("{", "["):
                    start = i
                    break
            if start is None:
                return None

            stack = []
            opening = s[start]
            stack.append(opening)
            in_str = False
            esc = False
            for j in range(start + 1, len(s)):
                c = s[j]
                if esc:
                    esc = False
                    continue
                if c == "\\":
                    esc = True
                    continue
                if c == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if c in ("{", "["):
                    stack.append(c)
                elif c == "}" and stack and stack[-1] == "{":
                    stack.pop()
                    if not stack:
                        candidate = s[start : j + 1]
                        try:
                            return json.loads(candidate)
                        except Exception:
                            return None
                elif c == "]" and stack and stack[-1] == "[":
                    stack.pop()
                    if not stack:
                        candidate = s[start : j + 1]
                        try:
                            return json.loads(candidate)
                        except Exception:
                            return None
            return None

        try:
            candidates = raw.get("candidates") or []
            if not candidates:
                return {}
            text = ""
            try:
                text = candidates[0]["content"]["parts"][0]["text"]
            except Exception:
                # accommodate different response shapes
                text = json.dumps(candidates[0])

            parsed = _extract_json_from_text(text)
            if isinstance(parsed, dict):
                return parsed
            return {}
        except Exception:
            return {}


service = IntentService()
