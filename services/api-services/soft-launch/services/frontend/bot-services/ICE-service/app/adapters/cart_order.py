"""Cart/Order adapter (HTTP-backed for real backends, file-backed for testing).

This adapter provides both:
- HTTP-backed implementation that calls the real Cart service backend
- File-backed stub for local testing without backend dependencies
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import aiohttp

from .base import CartOrderAdapter

logger = logging.getLogger(__name__)

STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "ice_cart_store.json"
STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


async def _read_store() -> Dict[str, Any]:
    def _read() -> Dict[str, Any]:
        if not STORE_PATH.exists():
            return {"drafts": {}, "reservations": {}, "orders": {}, "idempotency": {}}
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))

    return await asyncio.to_thread(_read)


async def _write_store(store: Dict[str, Any]) -> None:
    def _write() -> None:
        STORE_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")

    await asyncio.to_thread(_write)


@dataclass
class Draft:
    draft_id: str
    session_id: Optional[str]
    items: List[Dict[str, Any]] = field(default_factory=list)
    total_minor: int = 0
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)


class CartOrderServiceAdapter(CartOrderAdapter):
    """HTTP-backed cart/order adapter.

    If base_url is provided, calls real Cart service.
    Otherwise falls back to file-backed stub.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        order_base_url: Optional[str] = None,
        timeout: float = 5.0,
    ):
        self.base_url = base_url
        self.order_base_url = order_base_url
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
            return True
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/health") as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def create_or_update_draft(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a cart draft via Cart service."""
        if not self.use_http:
            return await self._create_or_update_draft_file(payload)
        
        try:
            session = await self._get_session()
            # POST /cart/create for new cart
            if not payload.get("draft_id"):
                async with session.post(
                    f"{self.base_url}/cart/create",
                    json={"session_id": payload.get("session_id"), "user_phone": payload.get("user_phone")},
                    headers={"X-Idempotency-Key": payload.get("idempotency_key", uuid4().hex)}
                ) as resp:
                    if resp.status in (200, 201):
                        cart = await resp.json()
                        return {"draft_id": cart.get("id"), **cart}
                    logger.error(f"Create cart failed: {resp.status}")
                    return {"status": "FAILED", "reason": f"HTTP {resp.status}"}
            
            # POST /cart/{id}/add for adding items to existing cart
            draft_id = payload.get("draft_id")
            items = payload.get("items", [])
            if items:
                # Add each item individually
                for item in items:
                    async with session.post(
                        f"{self.base_url}/cart/{draft_id}/add",
                        json={"product_id": item.get("product_id"), "qty": item.get("qty", 1)},
                        headers={"X-Idempotency-Key": payload.get("idempotency_key", uuid4().hex)}
                    ) as resp:
                        if resp.status not in (200, 201):
                            logger.warning(f"Add item failed: {resp.status}")
            
            # Return updated cart
            async with session.get(f"{self.base_url}/cart/session/{payload.get('session_id')}") as resp:
                if resp.status == 200:
                    carts = await resp.json()
                    if carts:
                        return {"draft_id": carts[0].get("id"), **carts[0]}
                    return {"status": "FAILED", "reason": "Cart not found"}
                logger.error(f"Fetch cart failed: {resp.status}")
                return {"status": "FAILED", "reason": f"HTTP {resp.status}"}
        except Exception as e:
            logger.error(f"Cart adapter error: {e}")
            return {"status": "FAILED", "reason": str(e)}

    async def reserve_items(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Reserve items from a cart (via checkout endpoint)."""
        if not self.use_http:
            return await self._reserve_items_file(payload)
        
        try:
            session = await self._get_session()
            draft_id = payload.get("draft_id") or payload.get("cart_id")
            async with session.post(
                f"{self.base_url}/cart/{draft_id}/checkout",
                json={},
                headers={"X-Idempotency-Key": payload.get("idempotency_key", uuid4().hex)}
            ) as resp:
                if resp.status in (200, 201):
                    checkout = await resp.json()
                    return {"reservation_id": draft_id, "status": "RESERVED", **checkout}
                if resp.status == 409:
                    return {"status": "FAILED", "reason": "OUT_OF_STOCK"}
                logger.error(f"Checkout failed: {resp.status}")
                return {"status": "FAILED", "reason": f"HTTP {resp.status}"}
        except Exception as e:
            logger.error(f"Reserve error: {e}")
            return {"status": "FAILED", "reason": str(e)}

    async def confirm_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Confirm an order and initiate payment with Order-Delivery service."""
        if not self.use_http:
            return await self._confirm_order_file(payload)

        if not self.order_base_url:
            return {"status": "FAILED", "reason": "ORDER_SERVICE_NOT_CONFIGURED"}

        session = await self._get_session()
        auth_headers = self._build_auth_headers(payload)
        idempotency_key = payload.get("idempotency_key") or uuid4().hex

        # Ensure payment number is numeric
        payment_number = self._normalize_payment_number(
            payload.get("payment_number") or payload.get("phone_number")
        )
        if not payment_number:
            return {"status": "FAILED", "reason": "INVALID_PAYMENT_NUMBER"}

        order_id = payload.get("order_id")
        order_body: Dict[str, Any] | None = None

        if not order_id:
            metadata = dict(payload.get("metadata") or {})
            if payload.get("pickup_location"):
                metadata["pickup_location"] = payload.get("pickup_location")
            if payload.get("delivery_location"):
                metadata["delivery_location"] = payload.get("delivery_location")

            order_payload = {
                "session_id": payload.get("session_id"),
                "user_phone": payload.get("user_phone") or payment_number,
                "user_id": payload.get("user_id"),
                "business_id": payload.get("business_id"),
                "delivery_method": payload.get("delivery_method", "pickup"),
                "total_amount": int(payload.get("total_amount", 0)),
                "currency": payload.get("currency", "ZMW"),
                "metadata": metadata,
            }

            async with session.post(
                f"{self.order_base_url}/orders/create",
                json=order_payload,
                headers={**auth_headers, "X-Idempotency-Key": idempotency_key},
            ) as resp:
                if resp.status not in (200, 201):
                    return {"status": "FAILED", "reason": f"ORDER_CREATE_HTTP_{resp.status}"}
                order_body = await resp.json()
                order_id = order_body.get("id")

        if not order_id:
            return {"status": "FAILED", "reason": "ORDER_ID_MISSING"}

        payment_payload = {
            "phoneNumber": payment_number,
            "provider": payload.get("payment_provider"),
            "currency": payload.get("currency", "ZMW"),
        }

        async with session.post(
            f"{self.order_base_url}/orders/{order_id}/initiate_payment",
            json=payment_payload,
            headers={**auth_headers, "X-Idempotency-Key": idempotency_key},
        ) as resp:
            if resp.status not in (200, 201):
                return {"status": "FAILED", "reason": f"PAYMENT_INIT_HTTP_{resp.status}", "order_id": order_id}
            payment_body = await resp.json()

        return {
            "status": "CONFIRMED",
            "order": order_body or {"id": order_id},
            "payment": payment_body,
        }
    
    # File-backed fallback methods
    async def _create_or_update_draft_file(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """File-backed draft creation."""
        store = await _read_store()

        idempotency = payload.get("idempotency_key")
        if idempotency and idempotency in store.get("idempotency", {}):
            return store["idempotency"][idempotency]

        draft_id = payload.get("draft_id") or f"draft-{uuid4().hex[:8]}"
        items = payload.get("items", [])
        total = 0
        for it in items:
            price = int(it.get("price_minor", 0))
            qty = int(it.get("qty", 1))
            total += price * qty

        draft = Draft(draft_id=draft_id, session_id=payload.get("session_id"), items=items, total_minor=total)
        store.setdefault("drafts", {})[draft_id] = asdict(draft)
        store.setdefault("idempotency", {})
        if idempotency:
            store["idempotency"][idempotency] = asdict(draft)

        await _write_store(store)
        return asdict(draft)

    async def _reserve_items_file(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """File-backed reservation."""
        store = await _read_store()
        idempotency = payload.get("idempotency_key")
        if idempotency and idempotency in store.get("idempotency", {}):
            return store["idempotency"][idempotency]

        items = payload.get("items")
        if not items and payload.get("draft_id"):
            draft = store.get("drafts", {}).get(payload.get("draft_id"))
            items = draft.get("items", []) if draft else []

        unavailable = [it for it in (items or []) if "OOS" in str(it.get("product_id", ""))]
        if unavailable:
            resp = {"status": "FAILED", "reason": "OUT_OF_STOCK", "unavailable": unavailable}
            if idempotency:
                store.setdefault("idempotency", {})[idempotency] = resp
                await _write_store(store)
            return resp

        reservation_id = f"res-{uuid4().hex[:8]}"
        reserved = {"reservation_id": reservation_id, "items": items or [], "status": "RESERVED", "expires_in": 300}
        store.setdefault("reservations", {})[reservation_id] = reserved
        if idempotency:
            store.setdefault("idempotency", {})[idempotency] = reserved
        await _write_store(store)
        return reserved

    async def _confirm_order_file(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """File-backed order confirmation."""
        store = await _read_store()
        idempotency = payload.get("idempotency_key")
        if idempotency and idempotency in store.get("idempotency", {}):
            return store["idempotency"][idempotency]

        items = []
        total = 0
        if payload.get("reservation_id"):
            res = store.get("reservations", {}).get(payload.get("reservation_id"))
            if not res:
                resp = {"status": "FAILED", "reason": "UNKNOWN_RESERVATION"}
                if idempotency:
                    store.setdefault("idempotency", {})[idempotency] = resp
                    await _write_store(store)
                return resp
            items = res.get("items", [])
        elif payload.get("draft_id"):
            dr = store.get("drafts", {}).get(payload.get("draft_id"))
            if not dr:
                resp = {"status": "FAILED", "reason": "UNKNOWN_DRAFT"}
                if idempotency:
                    store.setdefault("idempotency", {})[idempotency] = resp
                    await _write_store(store)
                return resp
            items = dr.get("items", [])

        for it in items:
            total += int(it.get("price_minor", 0)) * int(it.get("qty", 1))

        order_id = f"ORD-{uuid4().hex[:10]}"
        order = {"order_id": order_id, "status": "CONFIRMED", "items": items, "total_minor": total, "created_at": _now_iso()}
        store.setdefault("orders", {})[order_id] = order
        if idempotency:
            store.setdefault("idempotency", {})[idempotency] = order
        await _write_store(store)
        return order

