from __future__ import annotations

import uuid

from .base import AdapterResult, ProviderAdapter
from ..models import OutboundRequest


class StubProviderAdapter(ProviderAdapter):
    """Fallback adapter for providers not implemented yet.

    It does not deliver externally; it just returns a queued receipt.
    """

    async def send(self, request: OutboundRequest) -> AdapterResult:
        provider_message_id = f"{request.provider}_{uuid.uuid4().hex}"
        return AdapterResult(provider_message_id=provider_message_id, status="queued", retryable=False)
