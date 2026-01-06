from __future__ import annotations

from typing import Optional

from ..client import AsyncServiceClient
from ..models import Response


class DeliveryAdapter:
    def __init__(self, client: AsyncServiceClient) -> None:
        self._client = client

    async def generate_code(
        self,
        *,
        order_id: str,
        business_id: str,
        user_phone: Optional[str],
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Response:
        return await self._client.call(
            operation="delivery.generate_code",
            body={
                "order_id": order_id,
                "business_id": business_id,
                "user_phone": user_phone,
            },
            context={"correlation_id": correlation_id, "idempotency_key": idempotency_key},
        )

    async def confirm(
        self,
        *,
        delivery_code: str,
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Response:
        return await self._client.call(
            operation="delivery.confirm",
            body={"delivery_code": delivery_code},
            context={"correlation_id": correlation_id, "idempotency_key": idempotency_key},
        )
