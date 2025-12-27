from __future__ import annotations

import json
from typing import Any, Optional

from redis.asyncio import Redis
import logging

LOG = logging.getLogger("bot-ingress.cache")


class Cache:
    def __init__(self, redis: Redis, enabled: bool = True, *, read_only: bool = False) -> None:
        self._redis = redis
        self._enabled = enabled
        self._read_only = read_only

    async def get_json(self, key: str) -> Optional[dict]:
        if not self._enabled:
            return None
        raw = await self._redis.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        if not self._enabled:
            return
        # Respect read-only mode: avoid writes when enabled.
        if self._read_only:
            LOG.debug("redis_read_only enabled — skipping set_json for key=%s", key)
            return

        payload = json.dumps(value, ensure_ascii=False, default=str)
        await self._redis.set(key, payload, ex=ttl_seconds)


def cache_key_bot(phone: str) -> str:
    return f"cache:bot_by_phone:{phone}"


def cache_key_user(phone: str, business_id: str | None = None) -> str:
    if business_id:
        return f"cache:user_by_phone:{business_id}:{phone}"
    return f"cache:user_by_phone::{phone}"


def cache_key_capabilities(mode_name: str) -> str:
    return f"cache:capabilities_by_mode:{mode_name}"


def cache_key_session_context(session_id: str) -> str:
    return f"cache:session_context:{session_id}"
