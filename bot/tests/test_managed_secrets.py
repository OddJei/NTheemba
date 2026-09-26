from __future__ import annotations

from types import SimpleNamespace

import pytest
from ntheemba.adapters.secrets import SecretResolutionError
from ntheemba.config import Settings
from ntheemba.infrastructure.managed_secrets import (
    ManagedOrEnvironmentSecretResolver,
    load_managed_secrets,
)


@pytest.mark.asyncio
async def test_load_managed_secrets_uses_memory_fallback_without_database() -> None:
    storage = SimpleNamespace(managed_secrets={"managed:tradeflow-a": "private-value"})

    values = await load_managed_secrets(
        storage, Settings(environment="test", gateway_shared_secret="protected-key")
    )

    assert values == {"managed:tradeflow-a": "private-value"}


def test_managed_or_environment_resolver_keeps_managed_and_env_namespaces_separate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRADEFLOW_TEST_TOKEN", "environment-value")
    resolver = ManagedOrEnvironmentSecretResolver({"managed:tradeflow-a": "managed-value"})

    assert resolver.resolve("managed:tradeflow-a") == "managed-value"
    assert resolver.resolve("env:TRADEFLOW_TEST_TOKEN") == "environment-value"
    with pytest.raises(SecretResolutionError, match="configured secret is unavailable"):
        resolver.resolve("managed:tradeflow-missing")
