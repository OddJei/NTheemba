from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from src.app.config import get_http_timeout_seconds, get_order_delivery_base_url


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


async def delivery_is_confirmed(*, order_id: str, authorization: str | None, correlation_id: str | None) -> bool:
    """Return True if order-delivery reports delivery.status == confirmed.

    If there is no delivery record yet (404), treat as not confirmed.
    """
    base = get_order_delivery_base_url().rstrip("/")
    timeout = get_http_timeout_seconds()

    headers: dict[str, str] = {}
    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id
    if authorization:
        headers["Authorization"] = authorization

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(f"{base}/delivery/order/{order_id}", headers=headers)

    if r.status_code == 404:
        return False
    if r.status_code != 200:
        # Conservative default: if we cannot verify status, refuse refund.
        raise httpx.HTTPStatusError("order_delivery_lookup_failed", request=r.request, response=r)

    data: Any = r.json()
    status = data.get("status") if isinstance(data, dict) else None
    return status == "confirmed"
