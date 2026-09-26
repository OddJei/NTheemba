"""Configuration tests for Phase 12 persistence."""

from __future__ import annotations

import pytest
from ntheemba.config import Settings
from pydantic import ValidationError


def test_redis_backend_requires_url() -> None:
    with pytest.raises(ValidationError, match="redis_url"):
        Settings(session_backend="redis")


def test_postgres_backend_requires_dsn() -> None:
    with pytest.raises(ValidationError, match="postgres_dsn"):
        Settings(customer_backend="postgres")


def test_external_backends_accept_secret_connection_strings() -> None:
    settings = Settings(
        session_backend="redis",
        redis_url="redis://localhost:6379/0",
        customer_backend="postgres",
        postgres_dsn="postgresql://user:password@localhost/ntheemba",
    )

    assert settings.redis_dsn == "redis://localhost:6379/0"
    assert settings.postgres_connection_dsn is not None
    assert settings.postgres_connection_dsn.startswith("postgresql://")
    assert "password" not in repr(settings.postgres_dsn)


def test_pool_minimum_cannot_exceed_maximum() -> None:
    with pytest.raises(ValidationError, match="pool_min"):
        Settings(postgres_pool_min_size=11, postgres_pool_max_size=10)


def test_default_ttls_match_phase12_policy() -> None:
    settings = Settings()

    assert settings.session_ttl_seconds == 7 * 24 * 60 * 60
    assert settings.session_archive_ttl_seconds == 90 * 24 * 60 * 60
    assert settings.deduplication_ttl_seconds == 7 * 24 * 60 * 60
    assert settings.idempotency_ttl_seconds == 30 * 24 * 60 * 60
    assert settings.lock_ttl_seconds == 30
