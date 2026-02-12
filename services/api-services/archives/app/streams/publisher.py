from __future__ import annotations

import json
from typing import Any, Dict

from redis.asyncio import Redis

from ..core.config import Settings
from ..models import DlqEntry, OutboundRequest


async def publish_outbound(redis: Redis, settings: Settings, req: OutboundRequest) -> str:
    payload = req.model_dump()
    return await redis.xadd(settings.streams.outbound_requests, {"payload": json.dumps(payload)})


async def publish_dlq(redis: Redis, settings: Settings, entry: DlqEntry) -> str:
    return await redis.xadd(settings.streams.dlq, {"payload": entry.model_dump_json()})


def safe_error(code: str, message: str, *, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {"code": code, "message": message, "details": details or {}}
