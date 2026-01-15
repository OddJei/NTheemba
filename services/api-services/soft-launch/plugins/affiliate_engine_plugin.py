"""
Affiliate Engine plugin wrapper.

Provides intentful async methods over the shared transport client so callers avoid
raw httpx calls. Transport and middleware remain pluggable.
"""
from __future__ import annotations

from typing import Any, Dict

from contracts.python.soft_launch_client.client import AsyncServiceClient
from contracts.python.soft_launch_client.models import OperationSpec
from contracts.python.soft_launch_client.transports.httpx_async import HttpxAsyncTransport
from contracts.python.soft_launch_client.middleware.correlation import CorrelationMiddleware
from contracts.python.soft_launch_client.middleware.idempotency import IdempotencyMiddleware
from contracts.python.soft_launch_client.middleware.retry import RetryMiddleware


_AFFILIATE_OPS: Dict[str, OperationSpec] = {
    "affiliate.create": OperationSpec(service="affiliate-engine", method="POST", path="/affiliates"),
    "affiliate.list": OperationSpec(service="affiliate-engine", method="GET", path="/affiliates"),
    "affiliate.get": OperationSpec(service="affiliate-engine", method="GET", path="/affiliates/{affiliate_id}"),
    "link.create": OperationSpec(service="affiliate-engine", method="POST", path="/affiliates/{affiliate_id}/links"),
    "link.list": OperationSpec(service="affiliate-engine", method="GET", path="/affiliates/{affiliate_id}/links"),
    "track.click": OperationSpec(service="affiliate-engine", method="POST", path="/track/click"),
    "attribute.order": OperationSpec(service="affiliate-engine", method="POST", path="/attribute/order"),
    "payment.success": OperationSpec(service="affiliate-engine", method="POST", path="/events/payment-success"),
    "order.created": OperationSpec(service="affiliate-engine", method="POST", path="/events/order-created"),
    "earnings.get": OperationSpec(service="affiliate-engine", method="GET", path="/affiliates/{affiliate_id}/earnings"),
    "dashboard.get": OperationSpec(service="affiliate-engine", method="GET", path="/affiliates/{affiliate_id}/dashboard"),
}


class AffiliateEnginePlugin:
    """High-level async client for Affiliate Engine."""

    def __init__(self, client: AsyncServiceClient) -> None:
        self._client = client

    async def create_affiliate(self, payload: Dict[str, Any]):
        """Create affiliate (POST /affiliates).

        Parameters:
        - payload: affiliate fields (e.g., phone, name, country, metadata).

        Returns: httpx-like Response from transport.
        """
        return await self._client.call("affiliate.create", body=payload)

    async def list_affiliates(self):
        """List affiliates (GET /affiliates).

        Returns: Response with affiliates list payload.
        """
        return await self._client.call("affiliate.list")

    async def get_affiliate(self, affiliate_id: str):
        """Get affiliate by id (GET /affiliates/{affiliate_id}).

        Parameters:
        - affiliate_id: affiliate identifier.

        Returns: Response with affiliate record or 404.
        """
        return await self._client.call("affiliate.get", path_params={"affiliate_id": affiliate_id})

    async def create_link(self, affiliate_id: str, payload: Dict[str, Any]):
        """Create link for affiliate (POST /affiliates/{affiliate_id}/links).

        Parameters:
        - affiliate_id: affiliate identifier.
        - payload: link attributes (e.g., campaign name, redirect URL).

        Returns: Response with link record.
        """
        return await self._client.call("link.create", path_params={"affiliate_id": affiliate_id}, body=payload)

    async def list_links(self, affiliate_id: str):
        """List links for affiliate (GET /affiliates/{affiliate_id}/links).

        Parameters:
        - affiliate_id: affiliate identifier.

        Returns: Response with links array.
        """
        return await self._client.call("link.list", path_params={"affiliate_id": affiliate_id})

    async def track_click(self, payload: Dict[str, Any]):
        """Track click (POST /track/click).

        Parameters:
        - payload: includes event_id, link_id, ip/user_agent, etc.

        Returns: Response acknowledging tracking.
        """
        return await self._client.call("track.click", body=payload)

    async def attribute_order(self, payload: Dict[str, Any]):
        """Attribute order (POST /attribute/order).

        Parameters:
        - payload: order_id, affiliate_id or link context, amount, currency.

        Returns: Response with attribution result.
        """
        return await self._client.call("attribute.order", body=payload)

    async def payment_success(self, payload: Dict[str, Any]):
        """Notify payment success (POST /events/payment-success).

        Parameters:
        - payload: payment_id, order_id, amount_minor, currency, business_id.

        Returns: Response confirming event handling.
        """
        return await self._client.call("payment.success", body=payload)

    async def order_created(self, payload: Dict[str, Any]):
        """Notify order created (POST /events/order-created).

        Parameters:
        - payload: order_id, business_id, total_minor, currency, metadata.

        Returns: Response confirming event handling.
        """
        return await self._client.call("order.created", body=payload)

    async def get_earnings(self, affiliate_id: str):
        """Fetch earnings summary (GET /affiliates/{affiliate_id}/earnings).

        Parameters:
        - affiliate_id: affiliate identifier.

        Returns: Response with earnings aggregates.
        """
        return await self._client.call("earnings.get", path_params={"affiliate_id": affiliate_id})

    async def get_dashboard(self, affiliate_id: str, days: int = 30):
        """Fetch dashboard metrics (GET /affiliates/{affiliate_id}/dashboard?days=...).

        Parameters:
        - affiliate_id: affiliate identifier.
        - days: lookback window (default 30).

        Returns: Response with dashboard metrics.
        """
        return await self._client.call("dashboard.get", path_params={"affiliate_id": affiliate_id}, query={"days": str(days)})


def build_default_client(*, base_url: str = "http://127.0.0.1:8510", http_client=None) -> AsyncServiceClient:
    """Build a transport-backed client for Affiliate Engine with standard middleware."""
    transport = HttpxAsyncTransport(base_urls={"affiliate-engine": base_url}, http=http_client)
    return AsyncServiceClient(
        operation_map=_AFFILIATE_OPS,
        transport=transport,
        middlewares=[CorrelationMiddleware(), IdempotencyMiddleware(), RetryMiddleware()],
    )


def build_affiliate_plugin(base_url: str = "http://127.0.0.1:8510", http_client=None) -> AffiliateEnginePlugin:
    """Factory for Affiliate Engine plugin."""
    return AffiliateEnginePlugin(build_default_client(base_url=base_url, http_client=http_client))
