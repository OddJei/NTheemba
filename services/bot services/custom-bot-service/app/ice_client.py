from __future__ import annotations

import os
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger("custom_bot.ice_client")

ICE_BASE_URL = os.getenv("ICE_BASE_URL", "")
ICE_TIMEOUT = float(os.getenv("ICE_TIMEOUT", "2.0"))
ICE_MAX_RETRIES = int(os.getenv("ICE_MAX_RETRIES", "2"))


class IceClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None, max_retries: int | None = None):
        self.base_url = base_url or ICE_BASE_URL or ""
        self.timeout = float(timeout or ICE_TIMEOUT)
        self.max_retries = int(max_retries or ICE_MAX_RETRIES)

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    async def _post(self, path: str, json: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            raise ValueError("ICE not configured")

        url = self.base_url.rstrip("/") + path
        headers = {"Content-Type": "application/json"}

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, json=json, headers=headers)
                    if resp.status_code != 200:
                        logger.warning("ice_non_200", extra={"status": resp.status_code, "url": url, "attempt": attempt})
                        continue
                    return resp.json()
            except Exception as exc:
                logger.warning("ice_post_error", exc_info=exc, extra={"url": url, "attempt": attempt})
                continue

        raise ConnectionError(f"ICE call failed to {path} after {self.max_retries} attempts")

    async def create_order(self, *, session_id: str, oob_ref: str, event_id: str | None = None, extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
        payload = {"session_id": session_id, "oob_ref": oob_ref}
        if event_id:
            payload["event_id"] = event_id
        if extra:
            payload.update(extra)
        return await self._post("/ice/order/create", payload)

    async def trigger_payment(self, *, session_id: str, oob_ref: str, event_id: str | None = None, payment_method: str | None = None) -> Dict[str, Any]:
        payload = {"session_id": session_id, "oob_ref": oob_ref}
        if event_id:
            payload["event_id"] = event_id
        if payment_method:
            payload["payment_method"] = payment_method
        return await self._post("/ice/payment/trigger", payload)

    async def calculate_price(self, *, session_id: str, oob_ref: str, event_id: str | None = None) -> Dict[str, Any]:
        payload = {"session_id": session_id, "oob_ref": oob_ref}
        if event_id:
            payload["event_id"] = event_id
        return await self._post("/ice/cart/price", payload)

    async def get_payment_status(self, *, payment_id: str, session_id: str | None = None) -> Dict[str, Any]:
        # using a simple POST status endpoint for now
        payload = {"payment_id": payment_id}
        if session_id:
            payload["session_id"] = session_id
        return await self._post("/ice/payment/status", payload)

    async def validate_fulfillment_method(self, *, session_id: str, method: str, details: Dict[str, Any] | None = None) -> Dict[str, Any] | bool:
        payload = {"session_id": session_id, "method": method}
        if details:
            payload["details"] = details
        return await self._post("/ice/fulfillment/validate", payload)

    async def get_recommendations(self, *, session_id: str, count: int = 3) -> Dict[str, Any]:
        """Request simple recommendations (cache-friendly) from ICE.

        Returns a dict with `items` list. ICE may return cached/suggested products.
        """
        payload = {"session_id": session_id, "count": int(count)}
        return await self._post("/ice/recommendations", payload)

    async def get_categories(self, *, session_id: str, limit: int = 10) -> Dict[str, Any]:
        """Request top categories or catalog categories from ICE.

        Returns a dict with `categories` list.
        """
        payload = {"session_id": session_id, "limit": int(limit)}
        return await self._post("/ice/categories", payload)

    async def get_products(self, *, session_id: str, category: str | None = None, limit: int = 20) -> Dict[str, Any]:
        payload = {"session_id": session_id, "limit": int(limit)}
        if category is not None:
            payload["category"] = str(category)
        return await self._post("/ice/products", payload)

    async def get_product(self, *, session_id: str, product_id: str) -> Dict[str, Any]:
        """Fetch single product details (authoritative) from ICE."""
        payload = {"session_id": session_id, "product_id": str(product_id)}
        return await self._post("/ice/product", payload)

    async def hydrate(self, *, session_id: str, required_blobs: list[str], event_id: str | None = None) -> Dict[str, Any]:
        """Request ICE to hydrate a set of required blobs.

        `required_blobs` is a list of string keys the resolver understands (e.g. "product:p1").
        Returns a dict mapping blob keys to hydrated JSON values.
        """
        payload = {"session_id": session_id, "required_blobs": required_blobs}
        if event_id:
            payload["event_id"] = event_id
        return await self._post("/ice/hydrate", payload)

    async def track_affiliate_click(self, *, session_id: str, affiliate_code: str, source: str | None = None, event_id: str | None = None) -> Dict[str, Any]:
        """Record an affiliate/campaign click or entry via ICE."""
        payload = {"session_id": session_id, "affiliate_code": affiliate_code}
        if source:
            payload["source"] = source
        if event_id:
            payload["event_id"] = event_id
        return await self._post("/ice/affiliate/track_click", payload)

    async def resolve_token(self, *, token: str, buyer_phone: str | None = None, session_id: str | None = None, event_id: str | None = None) -> Dict[str, Any]:
        """Resolve an affiliate token through ICE which proxies to the affiliate engine.

        Returns product details on success. Raises ValueError if ICE not configured.
        """
        payload: Dict[str, Any] = {"token": token}
        if buyer_phone:
            payload["buyer_phone"] = buyer_phone
        if session_id:
            payload["session_id"] = session_id
        if event_id:
            payload["event_id"] = event_id
        return await self._post("/ice/token/resolve", payload)
