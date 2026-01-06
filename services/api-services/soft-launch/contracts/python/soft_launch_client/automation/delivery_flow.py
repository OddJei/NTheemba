from __future__ import annotations

from typing import Any, Dict, Optional

from ..adapters.delivery import DeliveryAdapter


class DeliveryPlugin:
    """Automation plugin: generate delivery code + confirm delivery."""

    def __init__(self, *, delivery: DeliveryAdapter) -> None:
        self._delivery = delivery

    async def generate_code(
        self,
        *,
        order_id: str,
        business_id: str,
        user_phone: Optional[str],
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        resp = await self._delivery.generate_code(
            order_id=order_id,
            business_id=business_id,
            user_phone=user_phone,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        return {"delivery": resp.body}

    async def confirm(
        self,
        *,
        delivery_code: str,
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        resp = await self._delivery.confirm(
            delivery_code=delivery_code,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        return {"delivery_confirmed": resp.body}
