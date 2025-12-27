from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

from ..core.config import get_settings
from ..models.schemas import IntentResponse


class IntentPublisher:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def publish_result(self, result: IntentResponse) -> None:
        settings = get_settings()
        payload = result.as_stream_dict()
        maxlen = settings.streams.maxlen
        await self.redis.xadd(
            settings.streams.results,
            payload,
            maxlen=maxlen,
            approximate=True if maxlen else False,
        )

    async def publish_dlq(self, *, request: dict[str, Any], error: str, attempts: int) -> None:
        settings = get_settings()
        payload = {
            "event_id": str(request.get("event_id") or request.get("request_id") or ""),
            "session_id": str(request.get("session_id") or ""),
            "error": str(error),
            "attempts": str(attempts),
            "payload": json.dumps(request, ensure_ascii=False, default=str),
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        maxlen = settings.streams.maxlen
        await self.redis.xadd(
            settings.streams.dlq,
            payload,
            maxlen=maxlen,
            approximate=True if maxlen else False,
        )
