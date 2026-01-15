"""
Cart service plugin wrapper providing intentful async methods.
"""
from __future__ import annotations

from typing import Any, Dict

from contracts.python.soft_launch_client.client import AsyncServiceClient
from contracts.python.soft_launch_client.models import OperationSpec
from contracts.python.soft_launch_client.transports.httpx_async import HttpxAsyncTransport
from contracts.python.soft_launch_client.middleware.correlation import CorrelationMiddleware
from contracts.python.soft_launch_client.middleware.idempotency import IdempotencyMiddleware
from contracts.python.soft_launch_client.middleware.retry import RetryMiddleware


_CART_OPS: Dict[str, OperationSpec] = {
    "cart.create": OperationSpec(service="cart", method="POST", path="/cart/create"),
    "cart.add": OperationSpec(service="cart", method="POST", path="/cart/{cart_id}/add"),
    "cart.update": OperationSpec(service="cart", method="PUT", path="/cart/{cart_id}/update"),
    "cart.remove_item": OperationSpec(service="cart", method="DELETE", path="/cart/{cart_id}/remove/{item_id}"),
    "cart.get_by_session": OperationSpec(service="cart", method="GET", path="/cart/session/{session_id}"),
    "cart.get_by_user": OperationSpec(service="cart", method="GET", path="/cart/user/{user_phone}"),
    "cart.checkout": OperationSpec(service="cart", method="POST", path="/cart/{cart_id}/checkout"),
}


class CartPlugin:
    """High-level async client for Cart service."""

    def __init__(self, client: AsyncServiceClient) -> None:
        self._client = client

    async def create(self, payload: Dict[str, Any]):
        """Create cart (POST /cart/create).

        Parameters:
        - payload: session/user identifiers and initial items.

        Returns: Response with cart record.
        """
        return await self._client.call("cart.create", body=payload)

    async def add_item(self, cart_id: str, payload: Dict[str, Any]):
        """Add item (POST /cart/{cart_id}/add).

        Parameters:
        - cart_id: cart identifier.
        - payload: item details (product_id/variant_id, quantity, price).

        Returns: Response with updated cart.
        """
        return await self._client.call("cart.add", path_params={"cart_id": cart_id}, body=payload)

    async def update(self, cart_id: str, payload: Dict[str, Any]):
        """Update cart (PUT /cart/{cart_id}/update).

        Parameters:
        - cart_id: cart identifier.
        - payload: updates to items or metadata.

        Returns: Response with updated cart.
        """
        return await self._client.call("cart.update", path_params={"cart_id": cart_id}, body=payload)

    async def remove_item(self, cart_id: str, item_id: str):
        """Remove item (DELETE /cart/{cart_id}/remove/{item_id}).

        Parameters:
        - cart_id: cart identifier.
        - item_id: item identifier within cart.

        Returns: Response with updated cart.
        """
        return await self._client.call("cart.remove_item", path_params={"cart_id": cart_id, "item_id": item_id})

    async def get_by_session(self, session_id: str):
        """Fetch cart by session (GET /cart/session/{session_id}).

        Parameters:
        - session_id: session identifier.

        Returns: Response with cart or 404.
        """
        return await self._client.call("cart.get_by_session", path_params={"session_id": session_id})

    async def get_by_user(self, user_phone: str):
        """Fetch cart by user phone (GET /cart/user/{user_phone}).

        Parameters:
        - user_phone: phone identifier.

        Returns: Response with cart list or 404.
        """
        return await self._client.call("cart.get_by_user", path_params={"user_phone": user_phone})

    async def checkout(self, cart_id: str, payload: Dict[str, Any]):
        """Checkout cart (POST /cart/{cart_id}/checkout).

        Parameters:
        - cart_id: cart identifier.
        - payload: checkout details (shipping, payment method, contact info).

        Returns: Response with order reference or validation errors.
        """
        return await self._client.call("cart.checkout", path_params={"cart_id": cart_id}, body=payload)


def build_default_client(*, base_url: str = "http://127.0.0.1:8530", http_client=None) -> AsyncServiceClient:
    """Build a transport-backed cart client with standard middleware."""
    transport = HttpxAsyncTransport(base_urls={"cart": base_url}, http=http_client)
    return AsyncServiceClient(
        operation_map=_CART_OPS,
        transport=transport,
        middlewares=[CorrelationMiddleware(), IdempotencyMiddleware(), RetryMiddleware()],
    )


def build_cart_plugin(base_url: str = "http://127.0.0.1:8530", http_client=None) -> CartPlugin:
    """Factory for Cart plugin."""
    return CartPlugin(build_default_client(base_url=base_url, http_client=http_client))
