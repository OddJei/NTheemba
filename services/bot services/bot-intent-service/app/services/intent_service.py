from __future__ import annotations

import json
import re
import time
from typing import Any, Iterable

import httpx

from ..core.config import get_settings
from ..models.schemas import Attachment, IntentInfo, IntentRequest, IntentResponse


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

        # Very lightweight intent mapping
        if any(k in text for k in ["buy", "purchase", "order", "i want", "add", "get me"]):
            intent = IntentInfo(id="add_item", name="Add Item", confidence=0.72)
            next_action = "reply"
        elif any(k in text for k in ["cancel", "stop", "abort"]):
            intent = IntentInfo(id="cancel_order", name="Cancel Order", confidence=0.75)
            next_action = "reply"
        elif any(k in text for k in ["track", "where is my", "delivery", "status"]):
            intent = IntentInfo(id="track_order", name="Track Order", confidence=0.74)
            next_action = "reply"
        elif any(k in text for k in ["help", "support", "agent", "human"]):
            intent = IntentInfo(id="request_support", name="Support", confidence=0.78)
            next_action = "outbound"
        else:
            intent = IntentInfo(id="unknown", name="Unknown", confidence=0.40)
            next_action = "reply"

        return intent, slots, next_action, diagnostics

    async def resolve(self, request: IntentRequest) -> IntentResponse:
        settings = get_settings()
        attachments = request.attachments or []
        self._validate_attachments(attachments)

        started = time.perf_counter()
        intent, slots, next_action, diagnostics = self._deterministic_resolve(request)

        # Optional Gemini enrichment (slot extraction / disambiguation).
        # Only attempt if enabled and API key exists.
        if settings.gemini.enabled and settings.gemini.api_key:
            try:
                api_key = (settings.gemini.api_key or "").split(",")[0].strip()
                if not api_key:
                    raise ValueError("Gemini enabled but no API key present")

                payload = self._build_payload(request)
                client = await self._get_client()
                diagnostics["gemini_attempted"] = True
                response = await client.post(
                    url=f"{settings.gemini.endpoint}/{settings.gemini.model}:generateContent",
                    params={"key": api_key},
                    json=payload,
                )
                response.raise_for_status()
                content = response.json()
                parsed = self._parse_response(content)
                if isinstance(parsed, dict) and parsed:
                    # Accept a structured response if present.
                    parsed_intent = parsed.get("intent")
                    if isinstance(parsed_intent, dict) and parsed_intent.get("id"):
                        intent = IntentInfo(
                            id=str(parsed_intent.get("id")),
                            name=parsed_intent.get("name"),
                            confidence=float(parsed_intent.get("confidence", intent.confidence)),
                        )
                    elif isinstance(parsed_intent, str):
                        intent = IntentInfo(id=parsed_intent, confidence=float(parsed.get("confidence", intent.confidence)))

                    parsed_slots = parsed.get("slots") or parsed.get("entities")
                    if isinstance(parsed_slots, dict):
                        slots = parsed_slots

                    if parsed.get("next_action") in {"reply", "outbound", "none"}:
                        next_action = parsed["next_action"]

                    diagnostics.update({"model_id": settings.gemini.model, "fallback": "gemini"})
                else:
                    diagnostics["gemini_parse"] = "empty_or_unparseable"
            except Exception as exc:
                diagnostics.update({"gemini_error": str(exc), "fallback": diagnostics.get("fallback", "deterministic")})

        latency_ms = int((time.perf_counter() - started) * 1000)
        diagnostics.setdefault("latency_ms", latency_ms)

        return IntentResponse(
            event_id=request.event_id,
            session_id=request.session_id,
            intent=intent,
            slots=slots,
            intent_required=bool(request.enriched_meta.get("intent_required", True)) if request.enriched_meta else True,
            next_action=next_action,  # type: ignore[arg-type]
            diagnostics=diagnostics,
            raw_input=request.raw_text,
        )

    @staticmethod
    def _build_payload(request: IntentRequest) -> dict:
        parts = []
        # Instruction: force strict JSON output so parsing is reliable.
        instruction = (
            "You are an intent+slot extraction service. "
            "Return ONLY valid JSON (no markdown, no extra text). "
            "Schema: {"
            "  \"intent\": {\"id\": string, \"name\": string|null, \"confidence\": number},"
            "  \"slots\": object,"
            "  \"next_action\": \"reply\"|\"outbound\"|\"none\""
            "}."
        )
        parts.append({"text": instruction})

        # user message
        parts.append({"text": f"User: {request.raw_text}"})
        # attachments - convert to inline content
        for attachment in request.attachments:
            parts.append({"text": f"[{attachment.name}]\n{attachment.content}"})
        return {
            "contents": [
                {
                    "role": "user",
                    "parts": parts,
                }
            ],
        }

    @staticmethod
    def _parse_response(raw: dict) -> dict:
        try:
            candidates = raw["candidates"]
            if not candidates:
                return {}
            content = candidates[0]["content"]["parts"][0]["text"]
            return json.loads(content)
        except (KeyError, ValueError, json.JSONDecodeError):
            return {}


service = IntentService()
