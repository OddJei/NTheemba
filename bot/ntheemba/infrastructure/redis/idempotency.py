"""Redis-backed external-action idempotency."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from ntheemba.infrastructure.redis.keys import RedisKeyspace
from ntheemba.ports.idempotency import (
    IdempotencyRecord,
    IdempotencyStatus,
    IdempotencyStore,
)

_FINISH_SCRIPT = """
local current = redis.call('get', KEYS[1])
if not current then return 0 end
local decoded = cjson.decode(current)
if decoded.owner_token ~= ARGV[1] then return 0 end
redis.call('set', KEYS[1], ARGV[2], 'EX', ARGV[3])
return 1
"""

_RELEASE_SCRIPT = """
local current = redis.call('get', KEYS[1])
if not current then return 0 end
local decoded = cjson.decode(current)
if decoded.owner_token ~= ARGV[1] or decoded.status ~= 'pending' then return 0 end
return redis.call('del', KEYS[1])
"""


class RedisIdempotencyStore(IdempotencyStore):
    def __init__(self, client: Any, keyspace: RedisKeyspace) -> None:
        self.client = client
        self.keyspace = keyspace

    async def claim(self, key: str, *, owner_token: str, ttl: timedelta) -> bool:
        self._validate(key, owner_token, ttl)
        record = IdempotencyRecord(key, IdempotencyStatus.PENDING, owner_token)
        result = await self.client.set(
            self.keyspace.idempotency(key),
            self._encode(record),
            ex=max(1, int(ttl.total_seconds())),
            nx=True,
        )
        return bool(result)

    async def get(self, key: str) -> IdempotencyRecord | None:
        payload = await self.client.get(self.keyspace.idempotency(key))
        return None if payload is None else self._decode(payload)

    async def complete(
        self,
        key: str,
        *,
        owner_token: str,
        result: Mapping[str, Any],
        ttl: timedelta,
    ) -> bool:
        return await self._finish(
            key,
            owner_token=owner_token,
            result=result,
            ttl=ttl,
            status=IdempotencyStatus.COMPLETED,
        )

    async def fail(
        self,
        key: str,
        *,
        owner_token: str,
        result: Mapping[str, Any],
        ttl: timedelta,
    ) -> bool:
        return await self._finish(
            key,
            owner_token=owner_token,
            result=result,
            ttl=ttl,
            status=IdempotencyStatus.FAILED,
        )

    async def release(self, key: str, *, owner_token: str) -> bool:
        result = await self.client.eval(
            _RELEASE_SCRIPT,
            1,
            self.keyspace.idempotency(key),
            owner_token,
        )
        return bool(result)

    async def _finish(
        self,
        key: str,
        *,
        owner_token: str,
        result: Mapping[str, Any],
        ttl: timedelta,
        status: IdempotencyStatus,
    ) -> bool:
        self._validate(key, owner_token, ttl)
        record = IdempotencyRecord(key, status, owner_token, result)
        changed = await self.client.eval(
            _FINISH_SCRIPT,
            1,
            self.keyspace.idempotency(key),
            owner_token,
            self._encode(record),
            max(1, int(ttl.total_seconds())),
        )
        return bool(changed)

    @staticmethod
    def _validate(key: str, owner_token: str, ttl: timedelta) -> None:
        if not key.strip() or not owner_token.strip():
            raise ValueError("key and owner_token must not be empty")
        if ttl <= timedelta(0):
            raise ValueError("ttl must be greater than zero")

    @staticmethod
    def _encode(record: IdempotencyRecord) -> bytes:
        return json.dumps(
            {
                "key": record.key,
                "status": record.status.value,
                "owner_token": record.owner_token,
                "result": dict(record.result),
                "updated_at": record.updated_at.isoformat(),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()

    @staticmethod
    def _decode(payload: bytes | str) -> IdempotencyRecord:
        raw = payload.decode() if isinstance(payload, bytes) else payload
        data = json.loads(raw)
        return IdempotencyRecord(
            key=str(data["key"]),
            status=IdempotencyStatus(str(data["status"])),
            owner_token=str(data["owner_token"]),
            result=dict(data.get("result", {})),
            updated_at=datetime.fromisoformat(str(data["updated_at"])).astimezone(UTC),
        )
