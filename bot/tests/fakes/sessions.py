"""In-memory implementations of session-related ports."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from copy import copy
from datetime import UTC, datetime, timedelta

from ntheemba.domain.session import Session
from ntheemba.ports.sessions import (
    DeduplicationKey,
    SessionConflictError,
    SessionKey,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _clone_session(session: Session) -> Session:
    """Clone the aggregate without copying immutable mapping proxies."""

    cloned = copy(session)
    cloned.order_draft = copy(session.order_draft) if session.order_draft else None
    cloned.booking_draft = copy(session.booking_draft) if session.booking_draft else None
    cloned.recent_history = list(session.recent_history)
    return cloned


class InMemorySessionRepository:
    """Revision-aware session repository for unit tests."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self.archived: list[Session] = []

    async def load(self, key: SessionKey) -> Session | None:
        session = self._sessions.get(key.value)
        return _clone_session(session) if session is not None else None

    async def save(
        self,
        session: Session,
        *,
        expected_revision: int | None,
    ) -> Session:
        key = SessionKey(session.business_id, session.customer_id)
        current = self._sessions.get(key.value)

        if current is None:
            if expected_revision is not None:
                raise SessionConflictError("new session expected_revision must be None")
            next_revision = 1
        else:
            if expected_revision != current.revision:
                raise SessionConflictError(
                    f"expected revision {expected_revision}, found {current.revision}"
                )
            next_revision = current.revision + 1

        saved = _clone_session(session)
        saved.revision = next_revision
        self._sessions[key.value] = _clone_session(saved)
        return _clone_session(saved)

    async def delete(self, key: SessionKey) -> None:
        self._sessions.pop(key.value, None)

    async def archive(self, session: Session) -> None:
        self.archived.append(_clone_session(session))


class InMemorySessionLockManager:
    """Per-session asyncio locks for deterministic concurrency tests."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    async def _get_lock(self, key: SessionKey) -> asyncio.Lock:
        async with self._guard:
            return self._locks.setdefault(key.value, asyncio.Lock())

    @asynccontextmanager
    async def lock(
        self,
        key: SessionKey,
        *,
        acquire_timeout: float | None = None,
    ) -> AsyncIterator[None]:
        lock = await self._get_lock(key)
        if acquire_timeout is None:
            await lock.acquire()
        else:
            await asyncio.wait_for(lock.acquire(), timeout=acquire_timeout)
        try:
            yield
        finally:
            lock.release()


class InMemoryDeduplicationStore:
    """TTL-based atomic claims for incoming message IDs."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._clock = clock
        self._claims: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def claim(
        self,
        key: DeduplicationKey,
        *,
        ttl: timedelta,
    ) -> bool:
        if ttl <= timedelta(0):
            raise ValueError("ttl must be greater than zero")
        now = self._clock()
        async with self._lock:
            expired = [value for value, expires_at in self._claims.items() if expires_at <= now]
            for value in expired:
                del self._claims[value]
            if key.value in self._claims:
                return False
            self._claims[key.value] = now + ttl
            return True

    async def release(self, key: DeduplicationKey) -> None:
        async with self._lock:
            self._claims.pop(key.value, None)
