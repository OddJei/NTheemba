"""Production-compatible in-memory persistence adapters."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import copy
from datetime import UTC, datetime, timedelta

from ntheemba.domain.session import Session
from ntheemba.ports.sessions import (
    DeduplicationKey,
    DeduplicationStore,
    SessionConflictError,
    SessionKey,
    SessionLockManager,
    SessionRepository,
)


def _clone(session: Session) -> Session:
    cloned = copy(session)
    cloned.order_draft = copy(session.order_draft) if session.order_draft else None
    cloned.booking_draft = copy(session.booking_draft) if session.booking_draft else None
    cloned.recent_history = list(session.recent_history)
    return cloned


class MemorySessionRepository(SessionRepository):
    def __init__(self) -> None:
        self._active: dict[str, Session] = {}
        self._archive: list[Session] = []
        self._guard = asyncio.Lock()

    async def load(self, key: SessionKey) -> Session | None:
        async with self._guard:
            session = self._active.get(key.value)
            return _clone(session) if session is not None else None

    async def save(self, session: Session, *, expected_revision: int | None) -> Session:
        key = SessionKey(session.business_id, session.customer_id).value
        async with self._guard:
            current = self._active.get(key)
            current_revision = current.revision if current is not None else None
            if current_revision != expected_revision:
                raise SessionConflictError("session revision changed before save")
            saved = _clone(session)
            saved.revision = (current_revision or 0) + 1
            self._active[key] = _clone(saved)
            return saved

    async def delete(self, key: SessionKey) -> None:
        async with self._guard:
            self._active.pop(key.value, None)

    async def archive(self, session: Session) -> None:
        async with self._guard:
            self._archive.append(_clone(session))

    async def ping(self) -> bool:
        return True


class MemorySessionLockManager(SessionLockManager):
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    @asynccontextmanager
    async def lock(
        self,
        key: SessionKey,
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
            raise TimeoutError(f"timed out acquiring session lock {key.value}") from error
        try:
            yield
        finally:
            lock.release()


class MemoryDeduplicationStore(DeduplicationStore):
    def __init__(self) -> None:
        self._claims: dict[str, datetime] = {}
        self._guard = asyncio.Lock()

    async def claim(self, key: DeduplicationKey, *, ttl: timedelta) -> bool:
        if ttl <= timedelta(0):
            raise ValueError("ttl must be greater than zero")
        now = datetime.now(UTC)
        async with self._guard:
            expired = [item for item, expires_at in self._claims.items() if expires_at <= now]
            for item in expired:
                self._claims.pop(item, None)
            if key.value in self._claims:
                return False
            self._claims[key.value] = now + ttl
            return True

    async def release(self, key: DeduplicationKey) -> None:
        async with self._guard:
            self._claims.pop(key.value, None)
