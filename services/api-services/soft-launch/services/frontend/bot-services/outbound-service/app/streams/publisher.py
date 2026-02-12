from __future__ import annotations

import json
from typing import Any, Dict, Optional

from redis.asyncio import Redis

from ..core.config import Settings
from ..models import DeliveryReceipt, DlqEntry


async def publish_receipt(redis: Redis, settings: Settings, receipt: DeliveryReceipt) -> None:
    if not settings.redis_stream_publish_enabled:
        return

    stream_name = f"{settings.platform_stream_prefix}{receipt.provider}"
    await redis.xadd(stream_name, {"payload": receipt.json()})


async def publish_dlq(redis: Redis, settings: Settings, entry: DlqEntry) -> None:
    if not settings.redis_stream_publish_enabled:
        return

    await redis.xadd(settings.outbound_dlq_stream, {"payload": entry.json()})


def safe_error(code: str, message: str, *, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"code": code, "message": message, "details": details or {}}
