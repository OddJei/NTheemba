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

    async def price_cart(self, *, session_id: str, oob_ref: str, event_id: str | None = None) -> Dict[str, Any]:
        """Alias for cart pricing to match handler expectations."""
        return await self.calculate_price(session_id=session_id, oob_ref=oob_ref, event_id=event_id)

    async def check_stock(self, *, session_id: str, items: list[Dict[str, Any]]) -> Dict[str, Any]:
        """Request stock validation/reservation for cart items."""
        payload = {"session_id": session_id, "items": items}
        return await self._post("/ice/cart/check_stock", payload)

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

    async def create_session(self, *, user_phone: str, bot_id: str | None = None, platform: str = "whatsapp", business_id: str | None = None, affiliate_id: str | None = None, event_id: str | None = None) -> Dict[str, Any]:
        """Ask ICE to create/resolve a session (ICE is authoritative for session lifecycle).

        Expected ICE behavior: proxy to bot-session, return at least `session_id`, optionally `cycle_id` and `current_stage`.
        """
        payload: Dict[str, Any] = {"user_phone": user_phone, "platform": platform}
        if bot_id:
            payload["bot_id"] = bot_id
        if business_id:
            payload["business_id"] = business_id
        if affiliate_id:
            payload["affiliate_id"] = affiliate_id
        if event_id:
            payload["event_id"] = event_id
        return await self._post("/ice/session/create", payload)

    async def update_stage(self, *, session_id: str, cycle_id: str | None = None, new_stage: str, context: Dict[str, Any] | None = None, event_id: str | None = None) -> Dict[str, Any]:
        """Request ICE to perform an authoritative stage upgrade.

        ICE should persist the upgrade (via bot-session) and may return merged hydrated blobs.
        """
        payload: Dict[str, Any] = {"session_id": session_id, "new_stage": new_stage}
        if cycle_id:
            payload["cycle_id"] = cycle_id
        if context is not None:
            payload["context"] = context
        if event_id:
            payload["event_id"] = event_id
        return await self._post("/ice/session/update_stage", payload)

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

    async def get_business_by_phone(self, *, phone: str, session_id: str | None = None) -> Dict[str, Any]:
        """Lookup business metadata by phone number (authoritative)."""
        payload: Dict[str, Any] = {"phone": str(phone)}
        if session_id:
            payload["session_id"] = session_id
        return await self._post("/ice/business/lookup_by_phone", payload)

    async def request_refund(self, *, session_id: str, order_id: str | None = None, reason: str | None = None, event_id: str | None = None) -> Dict[str, Any]:
        """Log a refund request in ICE and return a refund id/status.

        Expected ICE endpoint: POST /ice/refund/request
        """
        payload: Dict[str, Any] = {"session_id": session_id}
        if order_id:
            payload["order_id"] = order_id
        if reason:
            payload["reason"] = reason
        if event_id:
            payload["event_id"] = event_id
        return await self._post("/ice/refund/request", payload)

    async def notify_admin(self, *, session_id: str, subject: str, message: str, event_id: str | None = None) -> Dict[str, Any]:
        """Send a notification request to ICE to alert admin/staff about an incident.

        Expected ICE endpoint: POST /ice/admin/notify
        """
        payload: Dict[str, Any] = {"session_id": session_id, "subject": subject, "message": message}
        if event_id:
            payload["event_id"] = event_id
        return await self._post("/ice/admin/notify", payload)
