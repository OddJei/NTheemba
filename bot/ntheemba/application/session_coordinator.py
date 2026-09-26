"""Safe session loading, locking, expiry, rollback, and atomic commit."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from copy import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from ntheemba.domain.session import ConversationTurn, Session
from ntheemba.ports.sessions import SessionKey, SessionLockManager, SessionRepository


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _clone_session(session: Session) -> Session:
    """Create a detached aggregate snapshot without copying mapping proxies."""

    cloned = copy(session)
    cloned.order_draft = copy(session.order_draft) if session.order_draft else None
    cloned.booking_draft = copy(session.booking_draft) if session.booking_draft else None
    cloned.recent_history = list(session.recent_history)
    return cloned


@dataclass(slots=True)
class ManagedSession:
    """One locked session lifecycle owned by SessionCoordinator."""

    session: Session
    expected_revision: int | None
    repository: SessionRepository
    clock: Callable[[], datetime]
    ttl: timedelta
    history_limit: int
    _baseline: Session = field(repr=False)
    committed: bool = False

    def append_turn(self, turn: ConversationTurn) -> None:
        """Append a bounded conversation turn."""

        self.session.append_history(turn, maximum_entries=self.history_limit)

    def rollback(self) -> Session:
        """Discard mutations made since the last successful commit."""

        self.session = _clone_session(self._baseline)
        return self.session

    async def commit(self) -> Session:
        """Refresh activity, save atomically, and establish a new baseline."""

        now = self.clock()
        self.session.touch(now=now, ttl=self.ttl)
        saved = await self.repository.save(
            self.session,
            expected_revision=self.expected_revision,
        )
        self.session = saved
        self.expected_revision = saved.revision
        self._baseline = _clone_session(saved)
        self.committed = True
        return saved


class SessionCoordinator:
    """Coordinate session locks, creation, expiry, archive, and commits."""

    def __init__(
        self,
        repository: SessionRepository,
        locks: SessionLockManager,
        *,
        clock: Callable[[], datetime] = _utc_now,
        ttl: timedelta = timedelta(hours=24),
        lock_timeout: float | None = 10.0,
        history_limit: int = 20,
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("ttl must be greater than zero")
        if lock_timeout is not None and lock_timeout <= 0:
            raise ValueError("lock_timeout must be greater than zero")
        if history_limit <= 0:
            raise ValueError("history_limit must be greater than zero")
        self.repository = repository
        self.locks = locks
        self.clock = clock
        self.ttl = ttl
        self.lock_timeout = lock_timeout
        self.history_limit = history_limit

    @asynccontextmanager
    async def open(
        self,
        business_id: str,
        customer_id: str,
    ) -> AsyncIterator[ManagedSession]:
        """Lock and open one active session for processing."""

        key = SessionKey(business_id=business_id, customer_id=customer_id)
        async with self.locks.lock(key, acquire_timeout=self.lock_timeout):
            now = self.clock()
            loaded = await self.repository.load(key)
            expected_revision: int | None = None

            if loaded is not None:
                if loaded.status.value in {"closed", "expired"} or now >= loaded.expires_at:
                    if loaded.status.value not in {"closed", "expired"}:
                        loaded.expire(now=now)
                    await self.repository.archive(loaded)
                    await self.repository.delete(key)
                    loaded = None
                else:
                    expected_revision = loaded.revision

            session = loaded or Session.create(
                business_id,
                customer_id,
                now=now,
                ttl=self.ttl,
            )
            managed = ManagedSession(
                session=session,
                expected_revision=expected_revision,
                repository=self.repository,
                clock=self.clock,
                ttl=self.ttl,
                history_limit=self.history_limit,
                _baseline=_clone_session(session),
            )
            yield managed
