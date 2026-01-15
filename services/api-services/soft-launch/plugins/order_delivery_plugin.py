"""
Order + Delivery plugin wrapper.
"""
from __future__ import annotations

from typing import Any, Dict

from contracts.python.soft_launch_client.client import AsyncServiceClient
from contracts.python.soft_launch_client.models import OperationSpec
from contracts.python.soft_launch_client.transports.httpx_async import HttpxAsyncTransport
from contracts.python.soft_launch_client.middleware.correlation import CorrelationMiddleware
from contracts.python.soft_launch_client.middleware.idempotency import IdempotencyMiddleware
from contracts.python.soft_launch_client.middleware.retry import RetryMiddleware


_ORDER_DELIVERY_OPS: Dict[str, OperationSpec] = {
    "orders.create": OperationSpec(service="order-delivery", method="POST", path="/orders/create"),
    "orders.get": OperationSpec(service="order-delivery", method="GET", path="/orders/{order_id}"),
    "orders.mark_paid": OperationSpec(service="order-delivery", method="POST", path="/orders/{order_id}/mark_paid"),

    "delivery.initiate": OperationSpec(service="order-delivery", method="POST", path="/delivery/initiate/{order_id}"),
    "delivery.get": OperationSpec(service="order-delivery", method="GET", path="/delivery/{delivery_id}"),
    "delivery.by_order": OperationSpec(service="order-delivery", method="GET", path="/delivery/order/{order_id}"),
    "delivery.confirm": OperationSpec(service="order-delivery", method="POST", path="/delivery/{delivery_id}/confirm"),
    "delivery.by_user": OperationSpec(service="order-delivery", method="GET", path="/delivery/user/{user_phone}"),
}


class OrderDeliveryPlugin:
    """High-level async client for Order + Delivery service."""

    def __init__(self, client: AsyncServiceClient) -> None:
        self._client = client

    async def create_order(self, payload: Dict[str, Any]):
        """Create order (POST /orders/create).

        Parameters:
        - payload: order fields (items, amounts, user/contact, affiliate metadata).

        Returns: Response with order record.
        """
        return await self._client.call("orders.create", body=payload)

    async def get_order(self, order_id: str):
        """Get order (GET /orders/{order_id}).

        Parameters:
        - order_id: order identifier.

        Returns: Response with order record or 404.
        """
        return await self._client.call("orders.get", path_params={"order_id": order_id})

    async def mark_paid(self, order_id: str, payload: Dict[str, Any]):
        """Mark order paid (POST /orders/{order_id}/mark_paid).

        Parameters:
        - order_id: order identifier.
        - payload: payment metadata (payment_id, amount, currency).

        Returns: Response with updated order status.
        """
        return await self._client.call("orders.mark_paid", path_params={"order_id": order_id}, body=payload)

    async def initiate_delivery(self, order_id: str, payload: Dict[str, Any]):
        """Initiate delivery (POST /delivery/initiate/{order_id}).

        Parameters:
        - order_id: order identifier.
        - payload: delivery info (address/contact) to generate code.

        Returns: Response with delivery record and code hash.
        """
        return await self._client.call("delivery.initiate", path_params={"order_id": order_id}, body=payload)

    async def get_delivery(self, delivery_id: str):
        """Get delivery (GET /delivery/{delivery_id}).

        Parameters:
        - delivery_id: delivery identifier.

        Returns: Response with delivery record or 404.
        """
        return await self._client.call("delivery.get", path_params={"delivery_id": delivery_id})

    async def get_delivery_by_order(self, order_id: str):
        """Get delivery by order (GET /delivery/order/{order_id}).

        Parameters:
        - order_id: order identifier.

        Returns: Response with delivery record or 404.
        """
        return await self._client.call("delivery.by_order", path_params={"order_id": order_id})

    async def confirm_delivery(self, delivery_id: str, payload: Dict[str, Any]):
        """Confirm delivery (POST /delivery/{delivery_id}/confirm).

        Parameters:
        - delivery_id: delivery identifier.
        - payload: confirmation data (code provided by customer).

        Returns: Response with updated delivery/order status.
        """
        return await self._client.call("delivery.confirm", path_params={"delivery_id": delivery_id}, body=payload)

    async def get_deliveries_for_user(self, user_phone: str):
        """List deliveries for user phone (GET /delivery/user/{user_phone}).

        Parameters:
        - user_phone: phone identifier.

        Returns: Response with deliveries list.
        """
        return await self._client.call("delivery.by_user", path_params={"user_phone": user_phone})


def build_default_client(*, base_url: str = "http://127.0.0.1:8560", http_client=None) -> AsyncServiceClient:
    """Build a transport-backed Order+Delivery client with standard middleware."""
    transport = HttpxAsyncTransport(base_urls={"order-delivery": base_url}, http=http_client)
    return AsyncServiceClient(
        operation_map=_ORDER_DELIVERY_OPS,
        transport=transport,
        middlewares=[CorrelationMiddleware(), IdempotencyMiddleware(), RetryMiddleware()],
    )


def build_order_delivery_plugin(base_url: str = "http://127.0.0.1:8560", http_client=None) -> OrderDeliveryPlugin:
    """Factory for Order + Delivery plugin."""
    return OrderDeliveryPlugin(build_default_client(base_url=base_url, http_client=http_client))
