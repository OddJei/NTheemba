"""Redis-backed platform conversation sessions and distributed locks."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from copy import copy
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from time import monotonic
from typing import Any, Callable

from ntheemba.domain.platform_session import PlatformConversationSession
from ntheemba.infrastructure.redis.keys import RedisKeyspace
from ntheemba.infrastructure.serialization import (
    SerializationError,
    decode_platform_session,
    encode_platform_session,
)
from ntheemba.ports.platform_sessions import (
    PlatformSessionConflictError,
    PlatformSessionKey,
)

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


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RedisPlatformSessionRepository:
    def __init__(
        self,
        client: Any,
        keyspace: RedisKeyspace,
        *,
        session_ttl: timedelta,
        archive_ttl: timedelta,
        clock: Callable[[], datetime] = _utc_now,
        transaction_retries: int = 3,
    ) -> None:
        if session_ttl <= timedelta(0) or archive_ttl <= timedelta(0):
            raise ValueError("session and archive TTLs must be positive")
        if transaction_retries <= 0:
            raise ValueError("transaction_retries must be positive")
        self.client = client
        self.keyspace = keyspace
        self.session_ttl = session_ttl
        self.archive_ttl = archive_ttl
        self.clock = clock
        self.transaction_retries = transaction_retries

    async def load(self, key: PlatformSessionKey) -> PlatformConversationSession | None:
        payload = await self.client.get(
            self.keyspace.platform_session(key.channel_instance_id, key.customer_id)
        )
        if payload is None:
            return None
        try:
            return decode_platform_session(payload)
        except SerializationError as error:
            raise SerializationError(f"invalid platform session payload for {key.value}") from error

    async def save(
        self,
        session: PlatformConversationSession,
        *,
        expected_revision: int | None,
    ) -> PlatformConversationSession:
        redis_key = self.keyspace.platform_session(
            session.channel_instance_id,
            session.customer_id,
        )
        for attempt in range(self.transaction_retries):
            pipeline: Any = self.client.pipeline(transaction=True)
            try:
                async with pipeline:
                    await pipeline.watch(redis_key)
                    current_payload = await pipeline.get(redis_key)
                    current_revision: int | None = None
                    if current_payload is not None:
                        current_revision = decode_platform_session(current_payload).revision
                    if current_revision != expected_revision:
                        raise PlatformSessionConflictError(
                            "platform session revision changed before save"
                        )
                    next_revision = (current_revision or 0) + 1
                    saved = copy(session)
                    saved.revision = next_revision
                    remaining = int((saved.expires_at - self.clock()).total_seconds())
                    ttl_seconds = max(
                        1,
                        min(
                            int(self.session_ttl.total_seconds()),
                            remaining if remaining > 0 else 1,
                        ),
                    )
                    pipeline.multi()
                    pipeline.set(redis_key, encode_platform_session(saved), ex=ttl_seconds)
                    await pipeline.execute()
                    return saved
            except Exception as error:
                if type(error).__name__ != "WatchError":
                    raise
                if attempt + 1 >= self.transaction_retries:
                    raise PlatformSessionConflictError(
                        "platform session changed during save"
                    ) from None
        raise PlatformSessionConflictError("platform session could not be saved")

    async def delete(self, key: PlatformSessionKey) -> None:
        await self.client.delete(
            self.keyspace.platform_session(key.channel_instance_id, key.customer_id)
        )

    async def archive(self, session: PlatformConversationSession) -> None:
        key = self.keyspace.platform_session_archive(session.conversation_id, session.revision)
        await self.client.set(
            key,
            encode_platform_session(session),
            ex=int(self.archive_ttl.total_seconds()),
        )


class RedisPlatformSessionLockManager:
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
        key: PlatformSessionKey,
        *,
        acquire_timeout: float | None = None,
    ) -> AsyncIterator[None]:
        redis_key = self.keyspace.platform_lock(key.channel_instance_id, key.customer_id)
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
                raise TimeoutError(f"timed out acquiring platform lock {key.value}")
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
                raise RuntimeError(f"platform lock ownership was lost for {key.value}")

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
