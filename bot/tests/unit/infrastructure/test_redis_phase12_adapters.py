"""Adapter tests using an in-process Redis protocol double."""

from __future__ import annotations

from datetime import timedelta

import pytest
from ntheemba.domain.session import Session
from ntheemba.infrastructure.redis import (
    RedisDeduplicationStore,
    RedisIdempotencyStore,
    RedisKeyspace,
    RedisRuntimeProfileCache,
    RedisSessionLockManager,
    RedisSessionRepository,
)
from ntheemba.ports.idempotency import IdempotencyStatus
from ntheemba.ports.sessions import DeduplicationKey, SessionConflictError, SessionKey
from tests.fakes.redis_runtime import FakeRedis


def test_redis_keyspace_separates_environment_and_tenant_values() -> None:
    keyspace = RedisKeyspace("ntheemba", "production")

    session = keyspace.session("business:a", "customer:a")

    assert session.startswith("ntheemba:production:session:")
    assert "business:a" not in session
    assert "customer:a" not in session


def test_runtime_profile_key_includes_environment_business_channel_and_revision() -> None:
    keyspace = RedisKeyspace("ntheemba", "production")

    key = keyspace.runtime_profile("business:a", "channel:a", 42)

    assert key.startswith("ntheemba:production:runtime-profile:")
    assert key.endswith(":42")
    assert "business:a" not in key
    assert "channel:a" not in key


async def test_redis_session_repository_round_trip_and_revision() -> None:
    redis = FakeRedis()
    repository = RedisSessionRepository(
        redis,
        RedisKeyspace("ntheemba", "test"),
        session_ttl=timedelta(hours=24),
        archive_ttl=timedelta(days=30),
    )
    session = Session.create("harvest", "customer-1")

    saved = await repository.save(session, expected_revision=None)
    loaded = await repository.load(SessionKey("harvest", "customer-1"))

    assert saved.revision == 1
    assert loaded == saved
    with pytest.raises(SessionConflictError):
        await repository.save(session, expected_revision=None)


async def test_redis_session_archive_uses_bounded_ttl() -> None:
    redis = FakeRedis()
    keyspace = RedisKeyspace("ntheemba", "test")
    repository = RedisSessionRepository(
        redis,
        keyspace,
        session_ttl=timedelta(hours=24),
        archive_ttl=timedelta(days=30),
    )
    session = Session.create("harvest", "customer-1")

    await repository.archive(session)

    key = keyspace.session_archive(session.conversation_id, session.revision)
    assert redis.expiries[key] == 30 * 24 * 60 * 60


async def test_redis_deduplication_claims_only_once() -> None:
    redis = FakeRedis()
    store = RedisDeduplicationStore(redis, RedisKeyspace("ntheemba", "test"))
    key = DeduplicationKey("harvest", "message-1")

    assert await store.claim(key, ttl=timedelta(hours=1)) is True
    assert await store.claim(key, ttl=timedelta(hours=1)) is False
    await store.release(key)
    assert await store.claim(key, ttl=timedelta(hours=1)) is True


async def test_redis_idempotency_owner_controls_completion() -> None:
    redis = FakeRedis()
    store = RedisIdempotencyStore(redis, RedisKeyspace("ntheemba", "test"))

    assert await store.claim("booking-1", owner_token="owner-a", ttl=timedelta(days=7))
    assert not await store.complete(
        "booking-1",
        owner_token="owner-b",
        result={"request": "REQ-1"},
        ttl=timedelta(days=7),
    )
    assert await store.complete(
        "booking-1",
        owner_token="owner-a",
        result={"request": "REQ-1"},
        ttl=timedelta(days=7),
    )
    record = await store.get("booking-1")
    assert record is not None
    assert record.status == IdempotencyStatus.COMPLETED


async def test_redis_lock_releases_only_its_own_token() -> None:
    redis = FakeRedis()
    manager = RedisSessionLockManager(
        redis,
        RedisKeyspace("ntheemba", "test"),
        lock_ttl_seconds=6,
        retry_interval_seconds=0.01,
    )
    key = SessionKey("harvest", "customer-1")

    async with manager.lock(key, acquire_timeout=0.2):
        assert len(redis.values) == 1

    assert redis.values == {}


async def test_two_repository_instances_share_restart_safe_session_state() -> None:
    redis = FakeRedis()
    keyspace = RedisKeyspace("ntheemba", "test")
    before_restart = RedisSessionRepository(
        redis,
        keyspace,
        session_ttl=timedelta(days=7),
        archive_ttl=timedelta(days=90),
    )
    after_restart = RedisSessionRepository(
        redis,
        keyspace,
        session_ttl=timedelta(days=7),
        archive_ttl=timedelta(days=90),
    )
    session = Session.create("serahs-glow-lounge", "customer-1", ttl=timedelta(days=7))
    session.conversation_summary = "Booking knotless braids"

    saved = await before_restart.save(session, expected_revision=None)
    recovered = await after_restart.load(
        SessionKey("serahs-glow-lounge", "customer-1")
    )

    assert recovered is not None
    assert recovered.conversation_id == saved.conversation_id
    assert recovered.conversation_summary == "Booking knotless braids"
    assert recovered.expires_at == saved.expires_at


async def test_two_idempotency_instances_prevent_duplicate_external_action() -> None:
    redis = FakeRedis()
    keyspace = RedisKeyspace("ntheemba", "test")
    first_instance = RedisIdempotencyStore(redis, keyspace)
    second_instance = RedisIdempotencyStore(redis, keyspace)

    assert await first_instance.claim(
        "appointment:serahs:customer-1",
        owner_token="instance-a",
        ttl=timedelta(days=30),
    )
    assert not await second_instance.claim(
        "appointment:serahs:customer-1",
        owner_token="instance-b",
        ttl=timedelta(days=30),
    )


async def test_runtime_profile_cache_invalidates_revisioned_business_profile() -> None:
    redis = FakeRedis()
    cache = RedisRuntimeProfileCache(redis, RedisKeyspace("ntheemba", "test"))

    await cache.set("serah", "wa-serah", 7, '{"business":"serah"}', ttl_seconds=60)
    assert await cache.get("serah", "wa-serah", 7) == '{"business":"serah"}'

    await cache.invalidate("serah")

    assert await cache.get("serah", "wa-serah", 7) is None


async def test_runtime_profile_cache_separates_channels_for_same_business() -> None:
    redis = FakeRedis()
    cache = RedisRuntimeProfileCache(redis, RedisKeyspace("ntheemba", "test"))

    await cache.set("serah", "wa-serah-main", 7, '{"channel":"main"}', ttl_seconds=60)
    await cache.set("serah", "wa-serah-alt", 7, '{"channel":"alt"}', ttl_seconds=60)

    assert await cache.get("serah", "wa-serah-main", 7) == '{"channel":"main"}'
    assert await cache.get("serah", "wa-serah-alt", 7) == '{"channel":"alt"}'

    await cache.invalidate("serah")

    assert await cache.get("serah", "wa-serah-main", 7) is None
    assert await cache.get("serah", "wa-serah-alt", 7) is None
