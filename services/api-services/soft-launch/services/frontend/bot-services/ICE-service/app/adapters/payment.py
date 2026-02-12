"""Payment adapter (HTTP-backed for payment-revenue)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import uuid4

import aiohttp

from .base import PaymentAdapter

logger = logging.getLogger(__name__)


class PaymentRevenueAdapter(PaymentAdapter):
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
    def _normalize_payment_number(value: Any) -> Optional[str]:
        if value is None:
            return None
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        return digits or None

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
            logger.warning(f"Payment health check failed: {e}")
            return False

    async def create_payment_intent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.use_http:
            return {"status": "FAILED", "reason": "PAYMENT_SERVICE_NOT_CONFIGURED"}

        payment_number = self._normalize_payment_number(
            payload.get("payment_number") or payload.get("phone_number")
        )
        if not payment_number:
            return {"status": "FAILED", "reason": "INVALID_PAYMENT_NUMBER"}

        session = await self._get_session()
        headers = self._build_auth_headers(payload)
        headers["X-Idempotency-Key"] = payload.get("idempotency_key") or uuid4().hex

        body = {
            "depositId": payload.get("deposit_id"),
            "order_id": payload.get("order_id"),
            "business_id": payload.get("business_id"),
            "amount_minor": int(payload.get("amount_minor", 0)),
            "currency": payload.get("currency", "ZMW"),
            "phoneNumber": payment_number,
            "provider": payload.get("provider"),
            "metadata": payload.get("metadata", {}),
        }

        async with session.post(
            f"{self.base_url}/pawapay/deposits/initiate",
            json=body,
            headers=headers,
        ) as resp:
            if resp.status not in (200, 201):
                return {"status": "FAILED", "reason": f"HTTP_{resp.status}"}
            return await resp.json()

    async def fetch_payment_status(self, payment_ref: str) -> Dict[str, Any]:
        if not self.use_http:
            return {"status": "FAILED", "reason": "PAYMENT_SERVICE_NOT_CONFIGURED"}

        session = await self._get_session()
        headers = self._build_auth_headers({})
        async with session.get(
            f"{self.base_url}/pawapay/deposits/{payment_ref}",
            headers=headers,
        ) as resp:
            if resp.status != 200:
                return {"status": "FAILED", "reason": f"HTTP_{resp.status}"}
            return await resp.json()
