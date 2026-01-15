"""
Notification service plugin (Node gateway shape).
"""
from __future__ import annotations

from typing import Any, Dict

from contracts.python.soft_launch_client.client import AsyncServiceClient
from contracts.python.soft_launch_client.models import OperationSpec
from contracts.python.soft_launch_client.transports.httpx_async import HttpxAsyncTransport
from contracts.python.soft_launch_client.middleware.correlation import CorrelationMiddleware
from contracts.python.soft_launch_client.middleware.idempotency import IdempotencyMiddleware
from contracts.python.soft_launch_client.middleware.retry import RetryMiddleware


_NOTIFICATION_OPS: Dict[str, OperationSpec] = {
    "notification.send": OperationSpec(service="notification", method="POST", path="/notification/send"),
}


class NotificationPlugin:
    """High-level async client for Notification service."""

    def __init__(self, client: AsyncServiceClient) -> None:
        self._client = client

    async def send(self, payload: Dict[str, Any]):
        """Send notification (POST /notification/send).

        Parameters:
        - payload: channel (sms/email/in_app) and payload per channel (to, subject, message/html, etc.).

        Returns: Response with notification record (status sent/failed).
        """
        return await self._client.call("notification.send", body=payload)


def build_default_client(*, base_url: str = "http://127.0.0.1:8561", http_client=None) -> AsyncServiceClient:
    """Build a transport-backed Notification client with standard middleware."""
    transport = HttpxAsyncTransport(base_urls={"notification": base_url}, http=http_client)
    return AsyncServiceClient(
        operation_map=_NOTIFICATION_OPS,
        transport=transport,
        middlewares=[CorrelationMiddleware(), IdempotencyMiddleware(), RetryMiddleware()],
    )


def build_notification_plugin(base_url: str = "http://127.0.0.1:8561", http_client=None) -> NotificationPlugin:
    """Factory for Notification plugin."""
    return NotificationPlugin(build_default_client(base_url=base_url, http_client=http_client))
