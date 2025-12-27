from __future__ import annotations
from datetime import datetime, timezone
from typing import Tuple
from redis.asyncio import Redis
from ..core.config import Settings
import logging

LOG = logging.getLogger("bot-ingress.session")

SESSION_KEY_TEMPLATE = "session:{}"
SESSION_LOOKUP_KEY_TEMPLATE = "session_id_by_key:{}"


class SessionManager:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    async def ensure_first_processing(self, request_id: str) -> bool:
        key = f"idempotency:request:{request_id}"
        # In read-only mode we cannot write idempotency keys; assume processing is allowed.
        if getattr(self._settings, "redis_kv_read_only", False):
            LOG.debug("redis_kv_read_only enabled — skipping idempotency set for %s", request_id)
            return True

        inserted = await self._redis.set(key, "1", ex=self._settings.idempotency_ttl_seconds, nx=True)
        return bool(inserted)

    async def get_or_create_session(self, user_phone: str, bot_id: str, platform: str) -> Tuple[str, bool]:
        uniqueness_key = f"{user_phone}:{bot_id}:{platform}"
        lookup_key = SESSION_LOOKUP_KEY_TEMPLATE.format(uniqueness_key)
        session_id = await self._redis.get(lookup_key)
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        if session_id:
            session_key = SESSION_KEY_TEMPLATE.format(session_id)
            session_data = await self._redis.hgetall(session_key)
            if not session_data:
                session_id = None
            else:
                status = session_data.get("status", "")
                last_active_at = session_data.get("last_active_at")
                if last_active_at:
                    try:
                        last_active_dt = datetime.fromisoformat(last_active_at)
                    except ValueError:
                        last_active_dt = now
                else:
                    last_active_dt = now

                elapsed = (now - last_active_dt).total_seconds()
                if status != "active" or elapsed > self._settings.session_timeout_seconds:
                    if getattr(self._settings, "redis_kv_read_only", False):
                        LOG.debug("redis_kv_read_only enabled — would have reactivated session %s", session_id)
                        return session_id, True
                    await self._redis.hset(session_key, mapping={"status": "active", "last_active_at": now_iso})
                    return session_id, True

                if getattr(self._settings, "redis_kv_read_only", False):
                    LOG.debug("redis_kv_read_only enabled — skipping last_active_at update for %s", session_id)
                else:
                    await self._redis.hset(session_key, mapping={"last_active_at": now_iso})
                return session_id, False

        session_id = f"sess_{user_phone}_{bot_id}_{int(now.timestamp())}"
        session_key = SESSION_KEY_TEMPLATE.format(session_id)
        # In read-only mode we will not persist session metadata; return a generated session id.
        if getattr(self._settings, "redis_kv_read_only", False):
            LOG.debug("redis_kv_read_only enabled — generated ephemeral session_id=%s", session_id)
            return session_id, False

        await self._redis.hset(session_key, mapping={
            "status": "active",
            "started_at": now_iso,
            "last_active_at": now_iso,
            "user_phone": user_phone,
            "bot_id": bot_id,
            "platform": platform,
        })
        await self._redis.set(lookup_key, session_id)
        return session_id, False
