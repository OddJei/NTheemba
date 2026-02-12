from __future__ import annotations

import json
import os
import asyncio
from typing import Any, Callable, Tuple

import redis.asyncio as redis

DEFAULT_OOB = {
    "schema_version": "v1",
    "lock_version": 1,
    "last_event_id": None,
    "last_node_executed": None,
    "cart": {"items": [], "totals": {"subtotal": 0, "grand_total": 0}, "status": "building", "cart_version": 1},
    "meta": {},
}


class VersionConflict(Exception):
    pass


class OOBStore:
    def __init__(self, redis_url: str | None = None) -> None:
        url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._r = redis.from_url(url, decode_responses=True)

    def _key(self, session_id: str) -> str:
        return f"oob:{session_id}"

    async def get_oob(self, session_id: str) -> Tuple[dict[str, Any], int]:
        key = self._key(session_id)
        data = await self._r.hgetall(key)
        if not data or not data.get("payload"):
            return DEFAULT_OOB.copy(), 0
        payload = json.loads(data.get("payload"))
        version = int(data.get("version") or 0)
        return payload, version

    async def create_default_if_missing(self, session_id: str) -> Tuple[dict[str, Any], int]:
        key = self._key(session_id)
        exists = await self._r.exists(key)
        if exists:
            return await self.get_oob(session_id)
        payload = DEFAULT_OOB.copy()
        # initial version 1
        await self._r.hset(key, mapping={"payload": json.dumps(payload), "version": 1})
        return payload, 1

    async def cas_update(self, session_id: str, updater: Callable[[dict[str, Any]], dict[str, Any]], max_retries: int = 3) -> Tuple[dict[str, Any], int]:
        """
        Atomically update OOB using optimistic concurrency (WATCH/MULTI/EXEC).

        `updater` may be a sync or async callable that receives the current OOB dict and returns the updated dict.
        Returns the new (oob, version).
        Raises VersionConflict if unable to commit after retries.
        """
        key = self._key(session_id)
        r = self._r

        for attempt in range(max_retries):
            # read current
            data = await r.hgetall(key)
            if not data or not data.get("payload"):
                current = DEFAULT_OOB.copy()
                current_version = 0
            else:
                current = json.loads(data.get("payload"))
                current_version = int(data.get("version") or 0)

            # call updater
            new_oob = updater(current)
            if asyncio.iscoroutine(new_oob):
                new_oob = await new_oob

            new_version = max(1, current_version + 1)

            try:
                pipe = r.pipeline()
                await pipe.watch(key)
                # re-check version inside transaction
                cur_ver = await r.hget(key, "version")
                cur_ver_int = int(cur_ver or 0)
                if cur_ver_int != current_version:
                    await pipe.unwatch()
                    # contention — retry
                    await asyncio.sleep(0.05 * (attempt + 1))
                    continue

                pipe.multi()
                pipe.hset(key, mapping={"payload": json.dumps(new_oob), "version": new_version})
                await pipe.execute()
                return new_oob, new_version
            except redis.exceptions.WatchError:
                # someone changed the key, retry
                await asyncio.sleep(0.05 * (attempt + 1))
                continue
            finally:
                try:
                    await pipe.reset()
                except Exception:
                    pass

        raise VersionConflict(f"Failed to update OOB for {session_id} after {max_retries} attempts")

    async def set_last_event(self, session_id: str, event_id: str) -> Tuple[dict[str, Any], int]:
        def _upd(oob: dict[str, Any]) -> dict[str, Any]:
            oob = dict(oob)
            oob["last_event_id"] = event_id
            return oob

        return await self.cas_update(session_id, _upd)
