"""Redis connection lifecycle and health reporting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class RedisHealth:
    configured: bool
    connected: bool
    detail: str


class RedisRuntime:
    """Own the async Redis client for the application lifecycle."""

    def __init__(self, url: str, *, socket_timeout: float = 5.0) -> None:
        if not url.strip():
            raise ValueError("Redis URL must not be empty")
        self._url = url
        self._socket_timeout = socket_timeout
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            raise RuntimeError("Redis runtime has not been opened")
        return self._client

    async def open(self) -> None:
        if self._client is not None:
            return
        from redis.asyncio import Redis

        client = Redis.from_url(
            self._url,
            decode_responses=False,
            socket_connect_timeout=self._socket_timeout,
            socket_timeout=self._socket_timeout,
            health_check_interval=30,
        )
        try:
            await client.ping()
        except Exception:
            await client.aclose()
            raise
        self._client = client

    async def close(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            await client.aclose()

    async def ping(self) -> bool:
        if self._client is None:
            return False
        try:
            result: Any = await self._client.ping()
        except Exception:
            return False
        return bool(result)

    async def health(self) -> RedisHealth:
        connected = await self.ping()
        return RedisHealth(
            configured=True,
            connected=connected,
            detail="Redis ping succeeded" if connected else "Redis ping failed",
        )
