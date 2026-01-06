from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from ..client import AsyncServiceClient
from ..models import Response


class CartAdapter:
    def __init__(self, client: AsyncServiceClient) -> None:
        self._client = client

    async def create_cart(
        self,
        *,
        session_id: Optional[str],
        user_phone: Optional[str],
        business_id: str,
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Response:
        return await self._client.call(
            operation="cart.create",
            body={
                "session_id": session_id,
                "user_phone": user_phone,
                "business_id": business_id,
            },
            context={"correlation_id": correlation_id, "idempotency_key": idempotency_key},
        )

    async def add_item(
        self,
        *,
        cart_id: str,
        item: Dict[str, Any],
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Response:
        return await self._client.call(
            operation="cart.add_item",
            path_params={"cart_id": cart_id},
            body=item,
            context={"correlation_id": correlation_id, "idempotency_key": idempotency_key},
        )

    async def checkout(
        self,
        *,
        cart_id: str,
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Response:
        return await self._client.call(
            operation="cart.checkout",
            path_params={"cart_id": cart_id},
            body={},
            context={"correlation_id": correlation_id, "idempotency_key": idempotency_key},
        )
