"""Tests for Phase 2 session fakes and contracts."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from ntheemba.domain.session import Session
from ntheemba.ports.sessions import (
    DeduplicationKey,
    SessionConflictError,
    SessionKey,
)
from tests.fakes.sessions import (
    InMemoryDeduplicationStore,
    InMemorySessionLockManager,
    InMemorySessionRepository,
)


@pytest.mark.asyncio
async def test_repository_increments_revision_and_returns_detached_snapshots() -> None:
    repository = InMemorySessionRepository()
    session = Session.create(
        "BUS-1",
        "260970000001",
        conversation_id="CONV-1",
        now=datetime(2026, 7, 20, tzinfo=UTC),
    )

    saved = await repository.save(session, expected_revision=None)
    saved.conversation_summary = "local mutation"

    loaded = await repository.load(SessionKey("BUS-1", "260970000001"))

    assert saved.revision == 1
    assert loaded is not None
    assert loaded.conversation_summary == ""


@pytest.mark.asyncio
async def test_repository_rejects_stale_revision() -> None:
    repository = InMemorySessionRepository()
    session = Session.create("BUS-1", "260970000001")
    saved = await repository.save(session, expected_revision=None)

    await repository.save(saved, expected_revision=1)

    with pytest.raises(SessionConflictError):
        await repository.save(saved, expected_revision=1)


@pytest.mark.asyncio
async def test_lock_serializes_same_session_key() -> None:
    manager = InMemorySessionLockManager()
    key = SessionKey("BUS-1", "CUSTOMER-1")
    sequence: list[str] = []

    async def worker(name: str) -> None:
        async with manager.lock(key):
            sequence.append(f"{name}-start")
            await asyncio.sleep(0)
            sequence.append(f"{name}-end")

    await asyncio.gather(worker("a"), worker("b"))

    assert sequence in (
        ["a-start", "a-end", "b-start", "b-end"],
        ["b-start", "b-end", "a-start", "a-end"],
    )


@pytest.mark.asyncio
async def test_deduplication_claim_expires_after_ttl() -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)

    def clock() -> datetime:
        return now_holder[0]

    now_holder = [now]
    store = InMemoryDeduplicationStore(clock=clock)
    key = DeduplicationKey("BUS-1", "MSG-1")

    assert await store.claim(key, ttl=timedelta(minutes=5))
    assert not await store.claim(key, ttl=timedelta(minutes=5))

    now_holder[0] = now + timedelta(minutes=6)

    assert await store.claim(key, ttl=timedelta(minutes=5))
