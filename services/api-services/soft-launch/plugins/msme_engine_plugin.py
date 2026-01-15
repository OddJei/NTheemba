"""MSME Engine plugin wrapper.

Purpose:
- Hide raw HTTP paths; expose intentful methods (`register`, `login`, `get_business`, `update_business`).
- Use the shared transport client so HTTP/mock/other transports can be swapped via plugins.
- Ensure correlation/idempotency/retry middleware stay consistent across services.
"""
from __future__ import annotations

from typing import Any, Dict

from contracts.python.soft_launch_client.client import AsyncServiceClient
from contracts.python.soft_launch_client.models import OperationSpec
from contracts.python.soft_launch_client.transports.httpx_async import HttpxAsyncTransport
from contracts.python.soft_launch_client.middleware.correlation import CorrelationMiddleware
from contracts.python.soft_launch_client.middleware.idempotency import IdempotencyMiddleware
from contracts.python.soft_launch_client.middleware.retry import RetryMiddleware


# Local operation map for MSME Engine endpoints. Keeps the shared OPERATION_MAP untouched.
_MSME_OPS: Dict[str, OperationSpec] = {
    "auth.register": OperationSpec(service="msme-engine", method="POST", path="/auth/register"),
    "auth.login": OperationSpec(service="msme-engine", method="POST", path="/auth/login"),
    "auth.refresh": OperationSpec(service="msme-engine", method="POST", path="/auth/refresh"),
    "auth.logout": OperationSpec(service="msme-engine", method="POST", path="/auth/logout"),
    "auth.me": OperationSpec(service="msme-engine", method="GET", path="/auth/me"),
    "auth.phone": OperationSpec(service="msme-engine", method="GET", path="/auth/phone/{user_phone}"),
    "user.update": OperationSpec(service="msme-engine", method="PUT", path="/auth/user/{user_id}"),
    "user.delete": OperationSpec(service="msme-engine", method="DELETE", path="/auth/user/{user_id}"),

    "business.register": OperationSpec(service="msme-engine", method="POST", path="/business/register"),
    "business.get": OperationSpec(service="msme-engine", method="GET", path="/business/{id}"),
    "business.update": OperationSpec(service="msme-engine", method="PUT", path="/business/{id}"),
    "business.delete": OperationSpec(service="msme-engine", method="DELETE", path="/business/{id}"),
    "business.subscribe": OperationSpec(service="msme-engine", method="POST", path="/business/{id}/subscribe"),
    "business.subscription": OperationSpec(service="msme-engine", method="GET", path="/business/{id}/subscription"),
    "business.metadata": OperationSpec(service="msme-engine", method="GET", path="/business/{id}/metadata"),
    "business.by_phone": OperationSpec(service="msme-engine", method="GET", path="/business/phone/{phone_number}"),
    "business.reindex": OperationSpec(service="msme-engine", method="POST", path="/business/reindex"),
}


class MsmeEnginePlugin:
    """High-level async client for MSME Engine.

    Methods mirror core MSME flows and delegate to the pluggable transport layer.
    """

    def __init__(self, client: AsyncServiceClient) -> None:
        self._client = client

    async def register(self, payload: Dict[str, Any]):
        """Register a new MSME user/business (POST /auth/register).

        Parameters:
        - payload: auth + business fields (phone, password, business info).

        Returns: Response with tokens and user/business record.
        """
        return await self._client.call("auth.register", body=payload)

    async def login(self, payload: Dict[str, Any]):
        """Login to obtain tokens (POST /auth/login).

        Parameters:
        - payload: credentials (e.g., phone + password).

        Returns: Response with access/refresh tokens.
        """
        return await self._client.call("auth.login", body=payload)

    async def get_business(self, business_id: str):
        """Fetch business profile (GET /business/{id}).

        Parameters:
        - business_id: business identifier.

        Returns: Response with business record or 404.
        """
        return await self._client.call("business.get", path_params={"id": business_id})

    async def update_business(self, business_id: str, payload: Dict[str, Any]):
        """Update business profile (PUT /business/{id}).

        Parameters:
        - business_id: business identifier.
        - payload: fields to update (name, address, metadata, etc.).

        Returns: Response with updated business record.
        """
        return await self._client.call("business.update", path_params={"id": business_id}, body=payload)

    async def subscribe(self, business_id: str, payload: Dict[str, Any]):
        """Subscribe business (POST /business/{id}/subscribe).

        Parameters:
        - business_id: business identifier.
        - payload: subscription info (plan, payment ref).

        Returns: Response confirming subscription state.
        """
        return await self._client.call("business.subscribe", path_params={"id": business_id}, body=payload)


def build_default_client(*, base_url: str = "http://127.0.0.1:8500", http_client=None) -> AsyncServiceClient:
    """Build a transport-backed client with correlation/idempotency/retry middleware."""
    transport = HttpxAsyncTransport(base_urls={"msme-engine": base_url}, http=http_client)
    return AsyncServiceClient(
        operation_map=_MSME_OPS,
        transport=transport,
        middlewares=[CorrelationMiddleware(), IdempotencyMiddleware(), RetryMiddleware()],
    )


def build_msme_plugin(base_url: str = "http://127.0.0.1:8500", http_client=None) -> MsmeEnginePlugin:
    """Convenience factory for the MSME Engine plugin."""
    client = build_default_client(base_url=base_url, http_client=http_client)
    return MsmeEnginePlugin(client)
