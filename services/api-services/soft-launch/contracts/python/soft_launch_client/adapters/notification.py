from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..client import AsyncServiceClient
from ..models import Response


class NotificationAdapter:
    def __init__(self, client: AsyncServiceClient) -> None:
        self._client = client

    async def send(
        self,
        *,
        recipients: List[str],
        template: str,
        payload: Dict[str, Any],
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Response:
        return await self._client.call(
            operation="notify.send",
            body={"recipients": recipients, "template": template, "payload": payload},
            context={"correlation_id": correlation_id, "idempotency_key": idempotency_key},
        )
