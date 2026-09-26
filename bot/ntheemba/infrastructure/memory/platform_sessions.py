"""In-memory platform conversation persistence and locking."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import copy
from collections.abc import AsyncIterator

from ntheemba.domain.platform_session import PlatformConversationSession
from ntheemba.ports.platform_sessions import (
    PlatformSessionConflictError,
    PlatformSessionKey,
)


def _clone(session: PlatformConversationSession) -> PlatformConversationSession:
    return copy(session)


class MemoryPlatformSessionRepository:
    def __init__(self) -> None:
        self._active: dict[str, PlatformConversationSession] = {}
        self._archive: list[PlatformConversationSession] = []
        self._guard = asyncio.Lock()

    async def load(self, key: PlatformSessionKey) -> PlatformConversationSession | None:
        async with self._guard:
            session = self._active.get(key.value)
            return _clone(session) if session is not None else None

    async def save(
        self,
        session: PlatformConversationSession,
        *,
        expected_revision: int | None,
    ) -> PlatformConversationSession:
        key = PlatformSessionKey(session.channel_instance_id, session.customer_id).value
        async with self._guard:
            current = self._active.get(key)
            current_revision = current.revision if current is not None else None
            if current_revision != expected_revision:
                raise PlatformSessionConflictError("platform session revision changed before save")
            saved = _clone(session)
            saved.revision = (current_revision or 0) + 1
            self._active[key] = _clone(saved)
            return saved

    async def delete(self, key: PlatformSessionKey) -> None:
        async with self._guard:
            self._active.pop(key.value, None)

    async def archive(self, session: PlatformConversationSession) -> None:
        async with self._guard:
            self._archive.append(_clone(session))


class MemoryPlatformSessionLockManager:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    @asynccontextmanager
    async def lock(
        self,
        key: PlatformSessionKey,
        *,
        acquire_timeout: float | None = None,
    ) -> AsyncIterator[None]:
        async with self._guard:
            lock = self._locks.setdefault(key.value, asyncio.Lock())
        try:
            if acquire_timeout is None:
                await lock.acquire()
            else:
                await asyncio.wait_for(lock.acquire(), timeout=acquire_timeout)
        except TimeoutError as error:
            raise TimeoutError(f"timed out acquiring platform lock {key.value}") from error
        try:
            yield
        finally:
            lock.release()
