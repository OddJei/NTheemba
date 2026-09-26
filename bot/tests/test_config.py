"""Tests for application settings."""

from __future__ import annotations

import pytest
from ntheemba.config import Settings


def test_api_prefix_is_normalized() -> None:
    settings = Settings(api_prefix="api/v1/")

    assert settings.api_prefix == "/api/v1"


def test_optional_redis_url_can_be_empty() -> None:
    settings = Settings(redis_url="   ")

    assert settings.redis_url is None


def test_settings_allow_phase_zero_without_secrets() -> None:
    settings = Settings(
        environment="test",
        gateway_shared_secret=None,
        redis_url=None,
    )

    assert settings.gateway_shared_secret is None
    assert settings.redis_url is None


def test_trace_sampling_bounds_are_validated() -> None:
    from pydantic import ValidationError

    try:
        Settings(trace_sample_rate=1.1)
    except ValidationError:
        pass
    else:
        raise AssertionError("trace_sample_rate above 1 must be rejected")


def test_tracing_can_be_explicitly_disabled() -> None:
    settings = Settings(tracing_enabled=False, trace_export_enabled=False)

    assert settings.tracing_enabled is False
    assert settings.trace_export_enabled is False


def test_redis_backend_requires_redis_url() -> None:
    from pydantic import ValidationError

    try:
        Settings(session_backend="redis", redis_url=None)
    except ValidationError as error:
        assert "redis_url is required" in str(error)
    else:
        raise AssertionError("Redis backends must require redis_url")


def test_postgres_backend_requires_dsn() -> None:
    from pydantic import ValidationError

    try:
        Settings(customer_backend="postgres", postgres_dsn=None)
    except ValidationError as error:
        assert "postgres_dsn is required" in str(error)
    else:
        raise AssertionError("PostgreSQL backends must require postgres_dsn")


def test_phase12_default_ttls_keep_sessions_longer_than_locks() -> None:
    settings = Settings()

    assert settings.session_ttl_seconds == 7 * 24 * 60 * 60
    assert settings.session_archive_ttl_seconds == 90 * 24 * 60 * 60
    assert settings.idempotency_ttl_seconds == 30 * 24 * 60 * 60
    assert settings.lock_ttl_seconds == 30
    assert settings.session_ttl_seconds > settings.lock_ttl_seconds


def test_ncpc_base_url_rejects_literal_private_and_local_destinations() -> None:
    for url in (
        "https://localhost/v1",
        "https://127.0.0.1/v1",
        "https://10.0.0.5/v1",
        "https://169.254.169.254/latest/meta-data",
    ):
        try:
            Settings(ncpc_base_url=url)
        except Exception as error:
            assert "localhost" in str(error) or "non-public IP" in str(error)
        else:
            raise AssertionError(f"unsafe NCPC URL was accepted: {url}")


def test_self_service_tradeflow_onboarding_requires_strong_managed_secret_key() -> None:
    with pytest.raises(ValueError, match="gateway_shared_secret is required"):
        Settings(environment="test", tradeflow_self_service_onboarding_enabled=True)
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(
            environment="test",
            gateway_shared_secret="too-short",
            tradeflow_self_service_onboarding_enabled=True,
        )


def test_credentialed_tradeflow_onboarding_requires_managed_secret_key() -> None:
    with pytest.raises(ValueError, match="gateway_shared_secret is required"):
        Settings(
            environment="test",
            tradeflow_onboarding_tokens_json='{"BUSINESS-A":"enrollment-token"}',
        )


def test_development_compose_allows_only_the_exact_internal_ncpc_service_url() -> None:
    settings = Settings(environment="development", ncpc_base_url="http://ncpc:8080/")

    assert settings.ncpc_base_url == "http://ncpc:8080"

    for environment in ("staging", "production"):
        try:
            Settings(environment=environment, ncpc_base_url="http://ncpc:8080")
        except Exception as error:
            assert "absolute HTTPS endpoint" in str(error)
        else:
            raise AssertionError(f"internal NCPC URL was accepted in {environment}")


def test_gemini_is_default_off_and_does_not_require_key() -> None:
    settings = Settings(environment="test")

    assert settings.gemini_enabled is False
    assert settings.gemini_api_key is None
    assert settings.reply_localization_enabled is False
    assert settings.local_language_blend == 0.15
    assert settings.local_language_variant_list == ("bemba", "nyanja")


def test_gemini_enabled_requires_key_and_localization_requires_gemini() -> None:
    with pytest.raises(ValueError, match="gemini_api_key"):
        Settings(environment="test", gemini_enabled=True)

    with pytest.raises(ValueError, match="gemini_enabled"):
        Settings(environment="test", reply_localization_enabled=True)


def test_gemini_and_local_language_settings_are_validated() -> None:
    settings = Settings(
        environment="test",
        gemini_enabled=True,
        gemini_api_key="secret-key",
        gemini_model="models/gemini-test",
        reply_localization_enabled=True,
        local_language_blend=0.2,
        local_language_variants="nyanja,bemba",
    )

    assert settings.gemini_model == "gemini-test"
    assert settings.local_language_variant_list == ("nyanja", "bemba")

    with pytest.raises(ValueError, match="local_language_blend"):
        Settings(environment="test", local_language_blend=0.25)

    with pytest.raises(ValueError, match="unsupported local language"):
        Settings(environment="test", local_language_variants="bemba,tonga")
