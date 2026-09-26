"""Redis distributed session locks with ownership-safe renewal and release."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from secrets import token_urlsafe
from time import monotonic
from typing import Any

from ntheemba.infrastructure.redis.keys import RedisKeyspace
from ntheemba.ports.sessions import SessionKey, SessionLockManager

_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""

_RENEW_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('pexpire', KEYS[1], ARGV[2])
end
return 0
"""


class SessionLockTimeoutError(TimeoutError):
    """Raised when a distributed conversation lock cannot be acquired."""


class SessionLockLostError(RuntimeError):
    """Raised when lock ownership is lost before processing completes."""


class RedisSessionLockManager(SessionLockManager):
    def __init__(
        self,
        client: Any,
        keyspace: RedisKeyspace,
        *,
        lock_ttl_seconds: int = 30,
        retry_interval_seconds: float = 0.05,
    ) -> None:
        if lock_ttl_seconds < 5:
            raise ValueError("lock_ttl_seconds must be at least five seconds")
        if retry_interval_seconds <= 0:
            raise ValueError("retry_interval_seconds must be positive")
        self.client = client
        self.keyspace = keyspace
        self.lock_ttl_seconds = lock_ttl_seconds
        self.retry_interval_seconds = retry_interval_seconds

    @asynccontextmanager
    async def lock(
        self,
        key: SessionKey,
        *,
        acquire_timeout: float | None = None,
    ) -> AsyncIterator[None]:
        redis_key = self.keyspace.lock(key.business_id, key.customer_id)
        owner = token_urlsafe(24)
        deadline = None if acquire_timeout is None else monotonic() + acquire_timeout
        while True:
            acquired = await self.client.set(
                redis_key,
                owner.encode(),
                nx=True,
                px=self.lock_ttl_seconds * 1000,
            )
            if acquired:
                break
            if deadline is not None and monotonic() >= deadline:
                raise SessionLockTimeoutError(f"timed out acquiring session lock {key.value}")
            await asyncio.sleep(self.retry_interval_seconds)

        lost = asyncio.Event()
        renewer = asyncio.create_task(self._renew(redis_key, owner, lost))
        body_error: BaseException | None = None
        try:
            yield
        except BaseException as error:
            body_error = error
            raise
        finally:
            renewer.cancel()
            with suppress(asyncio.CancelledError):
                await renewer
            await self.client.eval(_RELEASE_SCRIPT, 1, redis_key, owner)
            if lost.is_set() and body_error is None:
                raise SessionLockLostError(f"session lock ownership was lost for {key.value}")

    async def _renew(self, redis_key: str, owner: str, lost: asyncio.Event) -> None:
        interval = max(1.0, self.lock_ttl_seconds / 3)
        while True:
            await asyncio.sleep(interval)
            renewed = await self.client.eval(
                _RENEW_SCRIPT,
                1,
                redis_key,
                owner,
                self.lock_ttl_seconds * 1000,
            )
            if not renewed:
                lost.set()
                return
