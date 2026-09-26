"""Redis-backed incoming message deduplication."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from ntheemba.infrastructure.redis.keys import RedisKeyspace
from ntheemba.ports.sessions import DeduplicationKey, DeduplicationStore


class RedisDeduplicationStore(DeduplicationStore):
    def __init__(self, client: Any, keyspace: RedisKeyspace) -> None:
        self.client = client
        self.keyspace = keyspace

    async def claim(self, key: DeduplicationKey, *, ttl: timedelta) -> bool:
        if ttl <= timedelta(0):
            raise ValueError("ttl must be greater than zero")
        result = await self.client.set(
            self.keyspace.deduplication(key.business_id, key.message_id),
            b"claimed",
            ex=max(1, int(ttl.total_seconds())),
            nx=True,
        )
        return bool(result)

    async def release(self, key: DeduplicationKey) -> None:
        await self.client.delete(self.keyspace.deduplication(key.business_id, key.message_id))
