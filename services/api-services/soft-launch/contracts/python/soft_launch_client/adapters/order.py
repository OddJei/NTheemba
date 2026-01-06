from __future__ import annotations

from typing import Any, Dict, Optional

from ..client import AsyncServiceClient
from ..models import Response


class OrderAdapter:
    def __init__(self, client: AsyncServiceClient) -> None:
        self._client = client

    async def create_order(
        self,
        *,
        business_id: str,
        user_phone: Optional[str],
        items: list[Dict[str, Any]],
        delivery_details: Optional[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]],
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Response:
        return await self._client.call(
            operation="order.create",
            body={
                "business_id": business_id,
                "user_phone": user_phone,
                "items": items,
                "delivery_details": delivery_details,
                "metadata": metadata,
            },
            context={"correlation_id": correlation_id, "idempotency_key": idempotency_key},
        )

    async def set_status(
        self,
        *,
        order_id: str,
        status: str,
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Response:
        return await self._client.call(
            operation="order.set_status",
            path_params={"order_id": order_id},
            body={"status": status},
            context={"correlation_id": correlation_id, "idempotency_key": idempotency_key},
        )
