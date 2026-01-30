from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

import httpx

from .base import AdapterResult, ProviderAdapter
from ..models import OutboundRequest


class HttpProviderAdapter(ProviderAdapter):
    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def send(self, request: OutboundRequest) -> AdapterResult:
        url: Optional[str] = request.callback_url
        if not url:
            maybe_url = request.provider_payload.get("url") if isinstance(request.provider_payload, dict) else None
            if isinstance(maybe_url, str) and maybe_url.strip():
                url = maybe_url.strip()

        if not url:
            return AdapterResult(
                provider_message_id=f"http_{uuid.uuid4().hex}",
                status="failed",
                retryable=False,
                provider_error={"code": "MISSING_URL", "message": "No callback_url or provider_payload.url provided"},
            )

        payload: Dict[str, Any] = request.provider_payload if isinstance(request.provider_payload, dict) else {"payload": request.provider_payload}
        headers = {"Idempotency-Key": request.event_id}

        try:
            resp = await self._client.post(url, json=payload, headers=headers)
            if 200 <= resp.status_code < 300:
                provider_message_id = resp.headers.get("X-Provider-Message-Id") or f"http_{uuid.uuid4().hex}"
                return AdapterResult(provider_message_id=provider_message_id, status="queued", retryable=False)

            retryable = resp.status_code >= 500
            return AdapterResult(
                provider_message_id=f"http_{uuid.uuid4().hex}",
                status="failed",
                retryable=retryable,
                provider_error={"code": f"HTTP_{resp.status_code}", "message": resp.text[:500]},
            )
        except httpx.TimeoutException:
            return AdapterResult(
                provider_message_id=f"http_{uuid.uuid4().hex}",
                status="failed",
                retryable=True,
                provider_error={"code": "TIMEOUT", "message": "HTTP provider timeout"},
            )
        except Exception as exc:
            return AdapterResult(
                provider_message_id=f"http_{uuid.uuid4().hex}",
                status="failed",
                retryable=True,
                provider_error={"code": "HTTP_ERROR", "message": str(exc)[:500]},
            )
