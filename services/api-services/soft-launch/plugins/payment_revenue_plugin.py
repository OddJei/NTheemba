"""
Payment + Revenue plugin wrapper.
"""
from __future__ import annotations

from typing import Any, Dict

from contracts.python.soft_launch_client.client import AsyncServiceClient
from contracts.python.soft_launch_client.models import OperationSpec
from contracts.python.soft_launch_client.transports.httpx_async import HttpxAsyncTransport
from contracts.python.soft_launch_client.middleware.correlation import CorrelationMiddleware
from contracts.python.soft_launch_client.middleware.idempotency import IdempotencyMiddleware
from contracts.python.soft_launch_client.middleware.retry import RetryMiddleware


_PAYMENT_OPS: Dict[str, OperationSpec] = {
    "payment.success": OperationSpec(service="payment-revenue", method="POST", path="/events/payment-success"),
}


class PaymentRevenuePlugin:
    """High-level async client for Payment + Revenue service."""

    def __init__(self, client: AsyncServiceClient) -> None:
        self._client = client

    async def payment_success(self, payload: Dict[str, Any]):
        """Process payment success (POST /events/payment-success).

        Parameters:
        - payload: payment_id, order_id, business_id, amount_minor, currency, affiliate context.

        Returns: Response with settlement record and downstream side effects result.
        """
        return await self._client.call("payment.success", body=payload)


def build_default_client(*, base_url: str = "http://127.0.0.1:8590", http_client=None) -> AsyncServiceClient:
    """Build a transport-backed Payment+Revenue client with standard middleware."""
    transport = HttpxAsyncTransport(base_urls={"payment-revenue": base_url}, http=http_client)
    return AsyncServiceClient(
        operation_map=_PAYMENT_OPS,
        transport=transport,
        middlewares=[CorrelationMiddleware(), IdempotencyMiddleware(), RetryMiddleware()],
    )


def build_payment_revenue_plugin(base_url: str = "http://127.0.0.1:8590", http_client=None) -> PaymentRevenuePlugin:
    """Factory for Payment + Revenue plugin."""
    return PaymentRevenuePlugin(build_default_client(base_url=base_url, http_client=http_client))
