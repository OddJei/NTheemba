"""Ports for temporary Ntheemba platform conversation state."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from ntheemba.domain.platform_session import PlatformConversationSession


@dataclass(frozen=True, slots=True)
class PlatformSessionKey:
    """Stable key for one customer on one Ntheemba platform channel."""

    channel_instance_id: str
    customer_id: str

    def __post_init__(self) -> None:
        if not self.channel_instance_id.strip() or not self.customer_id.strip():
            raise ValueError("channel_instance_id and customer_id are required")

    @property
    def value(self) -> str:
        return f"{self.channel_instance_id}:{self.customer_id}"


class PlatformSessionConflictError(RuntimeError):
    """Raised when optimistic platform-session revision checks fail."""


class PlatformSessionRepository(Protocol):
    async def load(self, key: PlatformSessionKey) -> PlatformConversationSession | None:
        """Load current platform session state."""

    async def save(
        self,
        session: PlatformConversationSession,
        *,
        expected_revision: int | None,
    ) -> PlatformConversationSession:
        """Atomically persist one platform session snapshot."""

    async def delete(self, key: PlatformSessionKey) -> None:
        """Delete active platform state."""

    async def archive(self, session: PlatformConversationSession) -> None:
        """Archive expired or closed platform state."""


class PlatformSessionLockManager(Protocol):
    def lock(
        self,
        key: PlatformSessionKey,
        *,
        acquire_timeout: float | None = None,
    ) -> AbstractAsyncContextManager[None]:
        """Lock one platform conversation key."""
