from __future__ import annotations

from typing import Any, Dict, Optional

from ..adapters.cart import CartAdapter
from ..adapters.order import OrderAdapter


class OrderCreationPlugin:
    """Automation plugin: create an order end-to-end.

    Soft-launch goal: one call from ICE for the whole order creation step.

    Note: This is a reference scaffold; align request/response shapes with your actual APIs.
    """

    def __init__(self, *, cart: CartAdapter, order: OrderAdapter) -> None:
        self._cart = cart
        self._order = order

    async def handle(
        self,
        *,
        business_id: str,
        user_phone: Optional[str],
        session_id: Optional[str],
        items: list[Dict[str, Any]],
        delivery_details: Optional[Dict[str, Any]],
        affiliate_code: Optional[str],
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        cart_resp = await self._cart.create_cart(
            session_id=session_id,
            user_phone=user_phone,
            business_id=business_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        cart_body = cart_resp.body or {}
        cart_id = cart_body.get("cart_id") or cart_body.get("id")

        for item in items:
            await self._cart.add_item(
                cart_id=str(cart_id),
                item=item,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
            )

        checkout_resp = await self._cart.checkout(
            cart_id=str(cart_id),
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        checkout_body = checkout_resp.body or {}

        order_resp = await self._order.create_order(
            business_id=business_id,
            user_phone=user_phone,
            items=checkout_body.get("items") or items,
            delivery_details=delivery_details,
            metadata={
                "session_id": session_id,
                "affiliate_code": affiliate_code,
                "cart_id": cart_id,
            },
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        return {
            "cart": cart_body,
            "checkout": checkout_body,
            "order": order_resp.body,
        }
