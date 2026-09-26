"""Deterministic controls for development and test dependency fakes."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")
Sleeper = Callable[[float], Awaitable[None]]

DEFAULT_FAKE_DEPENDENCIES: tuple[str, ...] = (
    "audit",
    "deduplication",
    "interpreter",
    "ncpc",
    "publisher",
    "session_lock",
    "session_repository",
    "tradeflow",
)

_MAX_LATENCY_MS = 30_000
_MAX_FAIL_NEXT = 100
_MAX_OPERATIONS = 20
_MAX_FAILURE_MESSAGE_LENGTH = 200
_OPERATION_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")


class FakeDependencyFailure(RuntimeError):
    """Raised when a configured fake dependency failure is triggered."""

    def __init__(self, dependency: str, operation: str, message: str) -> None:
        super().__init__(message)
        self.dependency = dependency
        self.operation = operation


@dataclass(frozen=True, slots=True)
class FakeDependencyBehavior:
    """Public immutable view of one fake dependency's behavior."""

    dependency: str
    latency_ms: int = 0
    fail_next: int = 0
    always_fail: bool = False
    failure_message: str = "Injected fake dependency failure"
    operations: tuple[str, ...] = ()


@dataclass(slots=True)
class _MutableBehavior:
    latency_ms: int = 0
    fail_next: int = 0
    always_fail: bool = False
    failure_message: str = "Injected fake dependency failure"
    operations: tuple[str, ...] = ()


class FakeDependencyController:
    """Store and apply deterministic fault plans for fake dependencies.

    The controller is safe for concurrent async use. A ``fail_next`` token is
    consumed atomically before latency is applied, ensuring exactly one caller
    receives each configured one-shot failure.
    """

    def __init__(
        self,
        dependencies: Iterable[str] = DEFAULT_FAKE_DEPENDENCIES,
        *,
        sleeper: Sleeper = asyncio.sleep,
    ) -> None:
        normalized = tuple(sorted({_normalize_dependency(value) for value in dependencies}))
        if not normalized:
            raise ValueError("at least one fake dependency is required")
        self._behaviors = {name: _MutableBehavior() for name in normalized}
        self._sleeper = sleeper
        self._lock = asyncio.Lock()

    @property
    def dependencies(self) -> tuple[str, ...]:
        """Return registered dependency names in stable order."""

        return tuple(self._behaviors)

    async def list_behaviors(self) -> tuple[FakeDependencyBehavior, ...]:
        """Return immutable snapshots for every registered dependency."""

        async with self._lock:
            return tuple(
                self._snapshot(name, behavior) for name, behavior in self._behaviors.items()
            )

    async def get_behavior(self, dependency: str) -> FakeDependencyBehavior:
        """Return one dependency's current behavior."""

        name = self._require_dependency(dependency)
        async with self._lock:
            return self._snapshot(name, self._behaviors[name])

    async def configure(
        self,
        dependency: str,
        *,
        latency_ms: int = 0,
        fail_next: int = 0,
        always_fail: bool = False,
        failure_message: str = "Injected fake dependency failure",
        operations: Iterable[str] = (),
    ) -> FakeDependencyBehavior:
        """Replace the complete behavior for one dependency."""

        name = self._require_dependency(dependency)
        validated_latency = _validate_latency(latency_ms)
        validated_fail_next = _validate_fail_next(fail_next)
        validated_message = _validate_failure_message(failure_message)
        validated_operations = _normalize_operations(operations)

        async with self._lock:
            behavior = _MutableBehavior(
                latency_ms=validated_latency,
                fail_next=validated_fail_next,
                always_fail=always_fail,
                failure_message=validated_message,
                operations=validated_operations,
            )
            self._behaviors[name] = behavior
            return self._snapshot(name, behavior)

    async def reset(self, dependency: str) -> FakeDependencyBehavior:
        """Restore one dependency to pass-through behavior."""

        name = self._require_dependency(dependency)
        async with self._lock:
            behavior = _MutableBehavior()
            self._behaviors[name] = behavior
            return self._snapshot(name, behavior)

    async def reset_all(self) -> tuple[FakeDependencyBehavior, ...]:
        """Restore all registered dependencies to pass-through behavior."""

        async with self._lock:
            for name in self._behaviors:
                self._behaviors[name] = _MutableBehavior()
            return tuple(
                self._snapshot(name, behavior) for name, behavior in self._behaviors.items()
            )

    async def before_call(self, dependency: str, operation: str) -> None:
        """Apply latency and failure behavior before a fake dependency call."""

        name = self._require_dependency(dependency)
        normalized_operation = _normalize_operation(operation)

        async with self._lock:
            behavior = self._behaviors[name]
            targeted = not behavior.operations or normalized_operation in behavior.operations
            latency_ms = behavior.latency_ms if targeted else 0
            should_fail = False
            failure_message = behavior.failure_message
            if targeted and behavior.always_fail:
                should_fail = True
            elif targeted and behavior.fail_next > 0:
                behavior.fail_next -= 1
                should_fail = True

        if latency_ms:
            await self._sleeper(latency_ms / 1000)
        if should_fail:
            raise FakeDependencyFailure(name, normalized_operation, failure_message)

    async def run(
        self,
        dependency: str,
        operation: str,
        action: Callable[[], Awaitable[T]],
    ) -> T:
        """Apply controls and then execute an asynchronous fake operation."""

        await self.before_call(dependency, operation)
        return await action()

    def _require_dependency(self, dependency: str) -> str:
        name = _normalize_dependency(dependency)
        if name not in self._behaviors:
            raise KeyError(name)
        return name

    @staticmethod
    def _snapshot(name: str, behavior: _MutableBehavior) -> FakeDependencyBehavior:
        return FakeDependencyBehavior(
            dependency=name,
            latency_ms=behavior.latency_ms,
            fail_next=behavior.fail_next,
            always_fail=behavior.always_fail,
            failure_message=behavior.failure_message,
            operations=behavior.operations,
        )


def _normalize_dependency(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    if not _OPERATION_PATTERN.fullmatch(normalized):
        raise ValueError("invalid fake dependency name")
    return normalized


def _normalize_operation(value: str) -> str:
    normalized = value.strip().lower()
    if not _OPERATION_PATTERN.fullmatch(normalized):
        raise ValueError("invalid fake operation name")
    return normalized


def _normalize_operations(values: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(sorted({_normalize_operation(value) for value in values}))
    if len(normalized) > _MAX_OPERATIONS:
        raise ValueError(f"operations cannot contain more than {_MAX_OPERATIONS} values")
    return normalized


def _validate_latency(value: int) -> int:
    if not 0 <= value <= _MAX_LATENCY_MS:
        raise ValueError(f"latency_ms must be between 0 and {_MAX_LATENCY_MS}")
    return value


def _validate_fail_next(value: int) -> int:
    if not 0 <= value <= _MAX_FAIL_NEXT:
        raise ValueError(f"fail_next must be between 0 and {_MAX_FAIL_NEXT}")
    return value


def _validate_failure_message(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("failure_message must not be empty")
    if len(normalized) > _MAX_FAILURE_MESSAGE_LENGTH:
        raise ValueError(f"failure_message cannot exceed {_MAX_FAILURE_MESSAGE_LENGTH} characters")
    return normalized
