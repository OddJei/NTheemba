from __future__ import annotations

import json
from typing import Any, Dict

from redis.asyncio import Redis

from ..core.config import settings


class IntentPublisher:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @staticmethod
    def _routing_key(session_id: str) -> str:
        return f"{settings.streams.routing_key_prefix}{session_id}"

    async def publish(self, *, bot_type: str, session_id: str, payload: Dict[str, Any]) -> None:
        if bot_type == "custom":
            stream = settings.streams.custom_queue
        else:
            stream = settings.streams.default_queue

        message = {
            "routing_key": self._routing_key(session_id),
            "payload": json.dumps(payload),
        }
        maxlen = settings.streams.maxlen
        await self.redis.xadd(stream, message, maxlen=maxlen, approximate=True if maxlen else False)
