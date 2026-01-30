from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..models import OutboundRequest


@dataclass
class AdapterResult:
    provider_message_id: str
    status: str  # queued|sent|delivered|failed
    retryable: bool = False
    provider_error: Optional[Dict[str, Any]] = None


class ProviderAdapter:
    async def send(self, request: OutboundRequest) -> AdapterResult:  # pragma: no cover
        raise NotImplementedError
