"""Redis cache for compiled business runtime profiles."""

from __future__ import annotations

from typing import Any

from ntheemba.infrastructure.redis.keys import RedisKeyspace


class RedisRuntimeProfileCache:
    """Store revisioned compiled runtime profiles outside PostgreSQL."""

    def __init__(self, client: Any, keyspace: RedisKeyspace) -> None:
        self.client = client
        self.keyspace = keyspace

    async def get(
        self,
        business_id: str,
        channel_instance_id: str,
        runtime_revision: int,
    ) -> str | None:
        payload = await self.client.get(
            self.keyspace.runtime_profile(
                business_id,
                channel_instance_id,
                runtime_revision,
            )
        )
        if payload is None:
            return None
        return payload.decode() if isinstance(payload, bytes) else str(payload)

    async def set(
        self,
        business_id: str,
        channel_instance_id: str,
        runtime_revision: int,
        payload: str,
        *,
        ttl_seconds: int,
    ) -> None:
        key = self.keyspace.runtime_profile(
            business_id,
            channel_instance_id,
            runtime_revision,
        )
        await self.client.set(key, payload, ex=ttl_seconds)
        index_key = self.keyspace.runtime_profile_index(business_id)
        current = await self.client.get(index_key)
        keys = set()
        if current is not None:
            decoded = current.decode() if isinstance(current, bytes) else str(current)
            keys.update(item for item in decoded.split("\n") if item)
        keys.add(key)
        await self.client.set(index_key, "\n".join(sorted(keys)), ex=ttl_seconds)

    async def invalidate(self, business_id: str) -> None:
        index_key = self.keyspace.runtime_profile_index(business_id)
        current = await self.client.get(index_key)
        if current is not None:
            decoded = current.decode() if isinstance(current, bytes) else str(current)
            for key in (item for item in decoded.split("\n") if item):
                await self.client.delete(key)
        await self.client.delete(index_key)
