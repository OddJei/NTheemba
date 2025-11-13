from __future__ import annotations

import json
from typing import Iterable

import httpx

from ..core.config import settings
from ..models.schemas import Attachment, IntentRequest, IntentResponse


class AttachmentLimitError(ValueError):
    """Raised when attachments exceed configured size budgets."""


class IntentService:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=settings.gemini.timeout_seconds)
        return self._client

    @staticmethod
    def _validate_attachments(attachments: Iterable[Attachment]) -> None:
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

    async def resolve(self, request: IntentRequest) -> IntentResponse:
        attachments = request.attachments or []
        self._validate_attachments(attachments)

        payload = self._build_payload(request)
        client = await self._get_client()
        response = await client.post(
            url=f"{settings.gemini.endpoint}/{settings.gemini.model}:generateContent",
            headers={"Authorization": f"Bearer {settings.gemini.api_key}"} if settings.gemini.api_key else None,
            json=payload,
        )
        response.raise_for_status()
        content = response.json()
        parsed = self._parse_response(content)
        return IntentResponse(
            request_id=request.request_id,
            session_id=request.session_id,
            intent=parsed.get("intent", "unknown"),
            confidence=float(parsed.get("confidence", 0.0)),
            entities=parsed.get("entities", {}),
            next_node=parsed.get("next_node"),
            clarifying_question=parsed.get("clarifying_question"),
            model=settings.gemini.model,
            tokens_used=parsed.get("tokens_used"),
            attachments=[attachment.name for attachment in attachments],
        )

    @staticmethod
    def _build_payload(request: IntentRequest) -> dict:
        parts = []
        # user message
        parts.append({"text": request.normalized_text})
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
