from __future__ import annotations

import os
import logging
from typing import Any

import httpx

from .intent_parser import Intent

logger = logging.getLogger("custom_bot.intent_client")

INTENT_SERVICE_URL = os.getenv("INTENT_SERVICE_URL", "http://localhost:5530/intent/resolve")
INTENT_TIMEOUT = float(os.getenv("INTENT_SERVICE_TIMEOUT", "1.5"))
INTENT_MAX_RETRIES = int(os.getenv("INTENT_SERVICE_MAX_RETRIES", "2"))


async def get_intents(
    *,
    event_id: str | None,
    session_id: str | None,
    raw_text: str,
    context: dict[str, Any] | None = None,
    required: bool = False,
) -> list[Intent]:
    """Call intent-service to resolve intents.

    Returns a list of Intent objects. On failure, returns an empty list.
    """
    payload = {
        "event_id": event_id,
        "session_id": session_id,
        "text": raw_text,
        "context": context or {},
        "required": bool(required),
    }

    headers = {"Content-Type": "application/json"}

    for attempt in range(1, INTENT_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=INTENT_TIMEOUT) as client:
                resp = await client.post(INTENT_SERVICE_URL, json=payload, headers=headers)
                if resp.status_code != 200:
                    logger.warning("intent_service_non_200", extra={"status": resp.status_code, "attempt": attempt})
                    continue
                body = resp.json()
                # Expecting shape: {"intents": [{"id":..., "confidence":..., "slots":{}}]}
                intents_raw = body.get("intents") or []
                intents: list[Intent] = []
                for it in intents_raw:
                    iid = it.get("id") or it.get("name")
                    slots = it.get("slots") or {}
                    if iid:
                        intents.append(Intent(id=str(iid), slots=slots))
                return intents
        except Exception as exc:
            logger.warning("intent_service_error", exc_info=exc, extra={"attempt": attempt})
            # continue to retry
            continue

    # After retries, return empty list — caller should fallback to local parser.
    return []
