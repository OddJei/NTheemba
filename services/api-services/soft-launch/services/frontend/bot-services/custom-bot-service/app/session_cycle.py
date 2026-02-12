from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Any

import redis.asyncio as redis

DEFAULT_REDIS = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


class SessionCycleStore:
    def __init__(self, redis_url: str | None = None):
        url = redis_url or DEFAULT_REDIS
        self._r = redis.from_url(url, decode_responses=True)

    def _key(self, session_id: str, cycle_type: str) -> str:
        return f"session:{session_id}:cycle:{cycle_type}"

    async def start_cycle(self, session_id: str, cycle_type: str, initiated_by_affiliate: bool = False, affiliate_code: str | None = None, affiliate_id: str | None = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        key = self._key(session_id, cycle_type)
        payload = {
            "session_id": session_id,
            "cycle_type": cycle_type,
            "started_at": _now_iso(),
            "completed_at": None,
            "initiated_by_affiliate": bool(initiated_by_affiliate),
            "affiliate_code": affiliate_code,
            "affiliate_id": affiliate_id,
            "meta": meta or {},
        }
        try:
            await self._r.hset(key, mapping={"payload": json.dumps(payload)})
        except Exception:
            # best-effort persistence; allow flows to continue without Redis
            pass
        return payload

    async def complete_cycle(self, session_id: str, cycle_type: str, extra_meta: dict[str, Any] | None = None) -> dict[str, Any] | None:
        key = self._key(session_id, cycle_type)
        try:
            data = await self._r.hgetall(key)
        except Exception:
            # Redis unavailable — return a best-effort payload
            payload = {
                "session_id": session_id,
                "cycle_type": cycle_type,
                "started_at": None,
                "completed_at": _now_iso(),
                "initiated_by_affiliate": False,
                "affiliate_code": None,
                "affiliate_id": None,
                "meta": extra_meta or {},
            }
            return payload

        if not data or not data.get("payload"):
            return None
        payload = json.loads(data.get("payload"))
        payload["completed_at"] = _now_iso()
        if extra_meta:
            payload_meta = dict(payload.get("meta") or {})
            payload_meta.update(extra_meta)
            payload["meta"] = payload_meta
        try:
            await self._r.hset(key, mapping={"payload": json.dumps(payload)})
        except Exception:
            pass
        return payload

    async def get_cycle(self, session_id: str, cycle_type: str) -> dict[str, Any] | None:
        key = self._key(session_id, cycle_type)
        try:
            data = await self._r.hgetall(key)
        except Exception:
            return None
        if not data or not data.get("payload"):
            return None
        return json.loads(data.get("payload"))


_DEFAULT_STORE: SessionCycleStore | None = None


def _default_store() -> SessionCycleStore:
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = SessionCycleStore()
    return _DEFAULT_STORE


async def start_cycle(session_id: str, cycle_type: str, **kwargs) -> dict[str, Any]:
    return await _default_store().start_cycle(session_id, cycle_type, **kwargs)


async def complete_cycle(session_id: str, cycle_type: str, **kwargs) -> dict[str, Any] | None:
    return await _default_store().complete_cycle(session_id, cycle_type, **kwargs)


async def get_cycle(session_id: str, cycle_type: str) -> dict[str, Any] | None:
    return await _default_store().get_cycle(session_id, cycle_type)
