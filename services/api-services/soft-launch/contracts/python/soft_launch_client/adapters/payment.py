from __future__ import annotations

from typing import Any, Dict, Optional

from ..client import AsyncServiceClient
from ..models import Response


class PaymentRevenueAdapter:
    def __init__(self, client: AsyncServiceClient) -> None:
        self._client = client

    async def initiate_payment(
        self,
        *,
        business_id: str,
        order_id: Optional[str],
        user_phone: Optional[str],
        amount: float,
        currency: str,
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Response:
        return await self._client.call(
            operation="payment.initiate",
            body={
                "business_id": business_id,
                "order_id": order_id,
                "user_phone": user_phone,
                "amount": amount,
                "currency": currency,
            },
            context={"correlation_id": correlation_id, "idempotency_key": idempotency_key},
        )

    async def verify_payment(
        self,
        *,
        payment_id: str,
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Response:
        return await self._client.call(
            operation="payment.verify",
            path_params={"payment_id": payment_id},
            body={},
            context={"correlation_id": correlation_id, "idempotency_key": idempotency_key},
        )
