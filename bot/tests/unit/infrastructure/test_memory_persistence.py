"""Tests for in-memory adapters matching the production persistence contracts."""

from __future__ import annotations

from datetime import timedelta

import pytest

from ntheemba.domain.session import Session
from ntheemba.infrastructure.memory import (
    MemoryDeduplicationStore,
    MemoryIdempotencyStore,
    MemorySessionLockManager,
    MemorySessionRepository,
)
from ntheemba.ports.idempotency import IdempotencyStatus
from ntheemba.ports.sessions import DeduplicationKey, SessionConflictError, SessionKey


async def test_memory_session_repository_enforces_revisions() -> None:
    repository = MemorySessionRepository()
    session = Session.create("harvest", "customer-1")

    saved = await repository.save(session, expected_revision=None)

    assert saved.revision == 1
    with pytest.raises(SessionConflictError):
        await repository.save(session, expected_revision=None)


async def test_memory_session_repository_returns_detached_snapshots() -> None:
    repository = MemorySessionRepository()
    saved = await repository.save(Session.create("harvest", "customer-1"), expected_revision=None)
    loaded = await repository.load(SessionKey("harvest", "customer-1"))

    assert loaded is not None
    loaded.conversation_summary = "mutated"
    loaded_again = await repository.load(SessionKey("harvest", "customer-1"))
    assert loaded_again is not None
    assert loaded_again.conversation_summary == ""
    assert saved.revision == loaded_again.revision


async def test_memory_deduplication_claims_once_and_can_release() -> None:
    store = MemoryDeduplicationStore()
    key = DeduplicationKey("harvest", "message-1")

    assert await store.claim(key, ttl=timedelta(minutes=5)) is True
    assert await store.claim(key, ttl=timedelta(minutes=5)) is False
    await store.release(key)
    assert await store.claim(key, ttl=timedelta(minutes=5)) is True


async def test_memory_idempotency_requires_owner_to_complete() -> None:
    store = MemoryIdempotencyStore()

    assert await store.claim("order-1", owner_token="owner-a", ttl=timedelta(hours=1))
    assert not await store.complete(
        "order-1",
        owner_token="owner-b",
        result={"request_id": "REQ-1"},
        ttl=timedelta(hours=1),
    )
    assert await store.complete(
        "order-1",
        owner_token="owner-a",
        result={"request_id": "REQ-1"},
        ttl=timedelta(hours=1),
    )
    record = await store.get("order-1")
    assert record is not None
    assert record.status == IdempotencyStatus.COMPLETED


async def test_memory_session_locks_serialize_same_customer() -> None:
    locks = MemorySessionLockManager()
    key = SessionKey("harvest", "customer-1")
    order: list[str] = []

    async def first() -> None:
        async with locks.lock(key):
            order.append("first-start")
            import asyncio

            await asyncio.sleep(0.01)
            order.append("first-end")

    async def second() -> None:
        import asyncio

        await asyncio.sleep(0)
        async with locks.lock(key):
            order.append("second")

    import asyncio

    await asyncio.gather(first(), second())
    assert order == ["first-start", "first-end", "second"]

async def test_storage_runtime_builds_coordinator_from_configured_adapters() -> None:
    from ntheemba.config import Settings
    from ntheemba.infrastructure.storage import StorageRuntime

    runtime = StorageRuntime(Settings(session_ttl_seconds=3600))
    await runtime.open()
    try:
        coordinator = runtime.build_session_coordinator()
        assert coordinator.repository is runtime.session_repository
        assert coordinator.locks is runtime.session_locks
        assert coordinator.ttl == timedelta(hours=1)
    finally:
        await runtime.close()


def test_storage_runtime_exposes_memory_marketplace_registry_by_default() -> None:
    from ntheemba.config import Settings
    from ntheemba.infrastructure.storage import build_storage_runtime

    runtime = build_storage_runtime(Settings(environment="test"))
    assert runtime.marketplace_registry.__class__.__name__ == "InMemoryMarketplaceRegistry"
