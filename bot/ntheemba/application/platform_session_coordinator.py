"""Lifecycle coordination for provider-neutral platform conversations."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from copy import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from ntheemba.domain.platform_session import PlatformConversationSession, PlatformConversationStage
from ntheemba.ports.platform_sessions import (
    PlatformSessionKey,
    PlatformSessionLockManager,
    PlatformSessionRepository,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _clone(session: PlatformConversationSession) -> PlatformConversationSession:
    return copy(session)


@dataclass(slots=True)
class ManagedPlatformSession:
    session: PlatformConversationSession
    expected_revision: int | None
    repository: PlatformSessionRepository
    clock: Callable[[], datetime]
    ttl: timedelta
    _baseline: PlatformConversationSession = field(repr=False)
    committed: bool = False

    def rollback(self) -> PlatformConversationSession:
        self.session = _clone(self._baseline)
        return self.session

    async def commit(self) -> PlatformConversationSession:
        self.session.touch(now=self.clock(), ttl=self.ttl)
        saved = await self.repository.save(
            self.session,
            expected_revision=self.expected_revision,
        )
        self.session = saved
        self.expected_revision = saved.revision
        self._baseline = _clone(saved)
        self.committed = True
        return saved


class PlatformSessionCoordinator:
    """Lock, expire, archive, and persist platform conversation state."""

    def __init__(
        self,
        repository: PlatformSessionRepository,
        locks: PlatformSessionLockManager,
        *,
        clock: Callable[[], datetime] = _utc_now,
        ttl: timedelta = timedelta(hours=24),
        lock_timeout: float | None = 10.0,
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("ttl must be greater than zero")
        if lock_timeout is not None and lock_timeout <= 0:
            raise ValueError("lock_timeout must be greater than zero")
        self.repository = repository
        self.locks = locks
        self.clock = clock
        self.ttl = ttl
        self.lock_timeout = lock_timeout

    @asynccontextmanager
    async def open(
        self,
        channel_instance_id: str,
        customer_id: str,
    ) -> AsyncIterator[ManagedPlatformSession]:
        key = PlatformSessionKey(channel_instance_id, customer_id)
        async with self.locks.lock(key, acquire_timeout=self.lock_timeout):
            now = self.clock()
            loaded = await self.repository.load(key)
            expected_revision: int | None = None
            if loaded is not None:
                if loaded.stage is PlatformConversationStage.CLOSED or loaded.expired(now=now):
                    await self.repository.archive(loaded)
                    await self.repository.delete(key)
                    loaded = None
                else:
                    expected_revision = loaded.revision
            session = loaded or PlatformConversationSession.create(
                channel_instance_id,
                customer_id,
                now=now,
                ttl=self.ttl,
            )
            managed = ManagedPlatformSession(
                session=session,
                expected_revision=expected_revision,
                repository=self.repository,
                clock=self.clock,
                ttl=self.ttl,
                _baseline=_clone(session),
            )
            yield managed
