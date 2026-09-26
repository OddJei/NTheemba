"""Port for durable external-action idempotency."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol


class IdempotencyStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    key: str
    status: IdempotencyStatus
    owner_token: str
    result: Mapping[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.key.strip() or not self.owner_token.strip():
            raise ValueError("idempotency key and owner token must not be empty")
        if self.updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")
        object.__setattr__(self, "result", MappingProxyType(dict(self.result)))


class IdempotencyStore(Protocol):
    async def claim(self, key: str, *, owner_token: str, ttl: timedelta) -> bool:
        """Claim an action key once."""

    async def get(self, key: str) -> IdempotencyRecord | None:
        """Load the current action record."""

    async def complete(
        self,
        key: str,
        *,
        owner_token: str,
        result: Mapping[str, Any],
        ttl: timedelta,
    ) -> bool:
        """Complete the action only when owned by owner_token."""

    async def fail(
        self,
        key: str,
        *,
        owner_token: str,
        result: Mapping[str, Any],
        ttl: timedelta,
    ) -> bool:
        """Mark the action failed only when owned by owner_token."""

    async def release(self, key: str, *, owner_token: str) -> bool:
        """Release a pending claim only when owned by owner_token."""
