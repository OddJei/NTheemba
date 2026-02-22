"""Delivery adapter (HTTP-backed for order-delivery)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import uuid4

import aiohttp

from .base import DeliveryAdapter

logger = logging.getLogger(__name__)


class DeliveryServiceAdapter(DeliveryAdapter):
    def __init__(self, base_url: Optional[str] = None, timeout: float = 5.0):
        self.base_url = base_url
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
        self.use_http = base_url is not None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self._session

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    @staticmethod
    def _build_auth_headers(payload: Dict[str, Any]) -> Dict[str, str]:
        token = payload.get("auth_token") or "dummy-token"
        headers: Dict[str, str] = {"Authorization": f"Bearer {token}"}
        if token == "dummy-token":
            headers["X-Role"] = payload.get("role", "admin")
            if payload.get("business_id"):
                headers["X-Business-Id"] = str(payload.get("business_id"))
        return headers

    async def health_check(self) -> bool:
        if not self.use_http:
            return False
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/health") as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Delivery health check failed: {e}")
            return False

    async def validate_delivery(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.use_http:
            return {"status": "FAILED", "reason": "DELIVERY_SERVICE_NOT_CONFIGURED"}

        session = await self._get_session()
        headers = self._build_auth_headers(payload)

        delivery_id = payload.get("delivery_id")
        order_id = payload.get("order_id")
        if delivery_id:
            url = f"{self.base_url}/delivery/{delivery_id}"
        elif order_id:
            url = f"{self.base_url}/delivery/order/{order_id}"
        else:
            return {"status": "FAILED", "reason": "MISSING_DELIVERY_ID"}

        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return {"status": "FAILED", "reason": f"HTTP_{resp.status}"}
            return await resp.json()

    async def create_delivery_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.use_http:
            return {"status": "FAILED", "reason": "DELIVERY_SERVICE_NOT_CONFIGURED"}

        order_id = payload.get("order_id")
        if not order_id:
            return {"status": "FAILED", "reason": "ORDER_ID_MISSING"}

        session = await self._get_session()
        headers = self._build_auth_headers(payload)
        headers["X-Idempotency-Key"] = payload.get("idempotency_key") or uuid4().hex

        async with session.post(
            f"{self.base_url}/delivery/initiate/{order_id}",
            headers=headers,
        ) as resp:
            if resp.status not in (200, 201):
                return {"status": "FAILED", "reason": f"HTTP_{resp.status}"}
            return await resp.json()

    async def set_order_delivery_location(self, order_id: str, chosen: str, *, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """Set or update delivery location for an order via Order-Delivery PUT endpoint.

        `chosen` may be an id, name or label. Returns JSON response or failure dict.
        """
        if not self.use_http:
            return {"status": "FAILED", "reason": "ORDER_SERVICE_NOT_CONFIGURED"}

        session = await self._get_session()
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        body = {"delivery_location": chosen}
        async with session.put(f"{self.base_url}/orders/{order_id}/delivery_location", json=body, headers=headers) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                logger.error("set_order_delivery_location failed %s %s", resp.status, text)
                return {"status": "FAILED", "reason": f"HTTP_{resp.status}", "detail": text}
            return await resp.json()

    async def set_order_payment_method(self, order_id: str, phone_number: str, *, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """Set or update the payment phone for an order via Order-Delivery PUT endpoint.

        Returns the JSON response or a failure dict.
        """
        if not self.use_http:
            return {"status": "FAILED", "reason": "ORDER_SERVICE_NOT_CONFIGURED"}

        session = await self._get_session()
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        body = {"phone_number": phone_number}
        async with session.put(f"{self.base_url}/orders/{order_id}/payment_method", json=body, headers=headers) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                logger.error("set_order_payment_method failed %s %s", resp.status, text)
                return {"status": "FAILED", "reason": f"HTTP_{resp.status}", "detail": text}
            return await resp.json()
