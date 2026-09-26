"""Ports for conversation persistence, locking, and message deduplication."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from ntheemba.domain.session import Session


@dataclass(frozen=True, slots=True)
class SessionKey:
    """Stable key for one business/customer conversation."""

    business_id: str
    customer_id: str

    def __post_init__(self) -> None:
        if not self.business_id.strip():
            raise ValueError("business_id must not be empty")
        if not self.customer_id.strip():
            raise ValueError("customer_id must not be empty")

    @property
    def value(self) -> str:
        """Return a storage-safe composite value."""

        return f"{self.business_id}:{self.customer_id}"


@dataclass(frozen=True, slots=True)
class DeduplicationKey:
    """Stable key for one incoming gateway message."""

    business_id: str
    message_id: str

    def __post_init__(self) -> None:
        if not self.business_id.strip():
            raise ValueError("business_id must not be empty")
        if not self.message_id.strip():
            raise ValueError("message_id must not be empty")

    @property
    def value(self) -> str:
        """Return a storage-safe composite value."""

        return f"{self.business_id}:{self.message_id}"


class SessionConflictError(RuntimeError):
    """Raised when optimistic session revision checks fail."""


class SessionRepository(Protocol):
    """Store and retrieve conversation sessions."""

    async def load(self, key: SessionKey) -> Session | None:
        """Load the current session snapshot."""

    async def save(
        self,
        session: Session,
        *,
        expected_revision: int | None,
    ) -> Session:
        """Atomically save and return the incremented snapshot."""

    async def delete(self, key: SessionKey) -> None:
        """Delete an active session."""

    async def archive(self, session: Session) -> None:
        """Store a completed or expired session in an archive."""


class SessionLockManager(Protocol):
    """Provide a distributed or in-process lock per session key."""

    def lock(
        self,
        key: SessionKey,
        *,
        acquire_timeout: float | None = None,
    ) -> AbstractAsyncContextManager[None]:
        """Return an async context manager that owns the session lock."""


class DeduplicationStore(Protocol):
    """Atomically claim incoming message IDs."""

    async def claim(
        self,
        key: DeduplicationKey,
        *,
        ttl: timedelta,
    ) -> bool:
        """Return True only for the first live claim."""

    async def release(self, key: DeduplicationKey) -> None:
        """Release a claim when processing must be retried from the beginning."""
