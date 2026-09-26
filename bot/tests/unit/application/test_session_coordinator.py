"""Tests for session lifecycle coordination."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from ntheemba.application.session_coordinator import SessionCoordinator
from ntheemba.domain.session import ConversationTurn, Session
from ntheemba.ports.sessions import SessionKey
from tests.fakes.sessions import InMemorySessionLockManager, InMemorySessionRepository


@pytest.mark.asyncio
async def test_coordinator_creates_and_commits_new_session() -> None:
    repository = InMemorySessionRepository()
    coordinator = SessionCoordinator(
        repository,
        InMemorySessionLockManager(),
        clock=lambda: datetime(2026, 7, 20, tzinfo=UTC),
    )

    async with coordinator.open("BUS-1", "CUSTOMER-1") as managed:
        managed.append_turn(ConversationTurn(role="customer", text="Hello"))
        saved = await managed.commit()

    assert saved.revision == 1
    loaded = await repository.load(SessionKey("BUS-1", "CUSTOMER-1"))
    assert loaded is not None
    assert loaded.recent_history[0].text == "Hello"


@pytest.mark.asyncio
async def test_coordinator_rolls_back_uncommitted_mutation() -> None:
    repository = InMemorySessionRepository()
    coordinator = SessionCoordinator(repository, InMemorySessionLockManager())

    async with coordinator.open("BUS-1", "CUSTOMER-1") as managed:
        managed.session.conversation_summary = "temporary"
        rolled_back = managed.rollback()

    assert rolled_back.conversation_summary == ""
    assert await repository.load(SessionKey("BUS-1", "CUSTOMER-1")) is None


@pytest.mark.asyncio
async def test_expired_session_is_archived_and_replaced() -> None:
    now = datetime(2026, 7, 21, tzinfo=UTC)
    repository = InMemorySessionRepository()
    old = Session.create(
        "BUS-1",
        "CUSTOMER-1",
        conversation_id="OLD-CONV",
        now=now - timedelta(days=2),
        ttl=timedelta(hours=1),
    )
    await repository.save(old, expected_revision=None)
    coordinator = SessionCoordinator(
        repository,
        InMemorySessionLockManager(),
        clock=lambda: now,
    )

    async with coordinator.open("BUS-1", "CUSTOMER-1") as managed:
        assert managed.session.conversation_id != "OLD-CONV"
        await managed.commit()

    assert len(repository.archived) == 1
    assert repository.archived[0].conversation_id == "OLD-CONV"


@pytest.mark.asyncio
async def test_coordinator_releases_lock_after_exception() -> None:
    repository = InMemorySessionRepository()
    coordinator = SessionCoordinator(repository, InMemorySessionLockManager())

    with pytest.raises(RuntimeError, match="injected"):
        async with coordinator.open("BUS-1", "CUSTOMER-1"):
            raise RuntimeError("injected")

    async with coordinator.open("BUS-1", "CUSTOMER-1") as managed:
        saved = await managed.commit()

    assert saved.revision == 1
