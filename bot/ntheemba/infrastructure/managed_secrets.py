"""Encrypted managed TradeFlow secrets for local self-service enrollment."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from ntheemba.adapters.secrets import EnvironmentSecretResolver, SecretResolutionError
from ntheemba.config import Settings


def _encryption_key(settings: Settings) -> str:
    """Derive a domain-separated database encryption key from protected runtime key material."""

    secret = settings.gateway_shared_secret
    if secret is None:
        raise RuntimeError("managed secret storage requires protected runtime key material")
    return hashlib.sha256(
        b"ntheemba-managed-tradeflow-secrets-v1\x00" + secret.get_secret_value().encode()
    ).hexdigest()


async def store_managed_secret(
    storage: Any, settings: Settings, reference: str, value: str
) -> None:
    """Encrypt and persist a generated secret outside integration configuration."""

    runtime = getattr(storage, "postgres_runtime", None)
    if runtime is None:
        values = getattr(storage, "managed_secrets", None)
        if values is None:
            values = {}
            storage.managed_secrets = values
        values[reference] = value
        return
    async with runtime.pool.connection() as connection:
        await connection.execute(
            """
            INSERT INTO managed_integration_secrets (secret_reference, ciphertext)
            VALUES (%s, pgp_sym_encrypt(%s, %s))
            ON CONFLICT (secret_reference) DO UPDATE SET ciphertext = EXCLUDED.ciphertext,
                updated_at = NOW()
            """,
            (reference, value, _encryption_key(settings)),
        )


async def load_managed_secrets(storage: Any, settings: Settings) -> dict[str, str]:
    """Load decrypted managed credentials into the worker's private process memory.

    The cache is built only at worker startup. Values are never written to an
    integration record, log, queue payload, or browser response.
    """

    runtime = getattr(storage, "postgres_runtime", None)
    if runtime is None:
        return dict(getattr(storage, "managed_secrets", {}) or {})
    async with runtime.pool.connection() as connection:
        cursor = await connection.execute(
            """
            SELECT secret_reference, pgp_sym_decrypt(ciphertext, %s)::text AS secret_value
              FROM managed_integration_secrets
             WHERE secret_reference LIKE 'managed:tradeflow-%%'
            """,
            (_encryption_key(settings),),
        )
        rows = await cursor.fetchall()
    values: dict[str, str] = {}
    for row in rows:
        reference, value = (
            (row["secret_reference"], row["secret_value"])
            if isinstance(row, Mapping)
            else (row[0], row[1])
        )
        if isinstance(reference, str) and isinstance(value, str) and value:
            values[reference] = value
    return values


class ManagedOrEnvironmentSecretResolver:
    """Resolve generated managed references first, then ordinary env references."""

    def __init__(self, managed_values: Mapping[str, str]) -> None:
        self._managed_values = dict(managed_values)
        self._environment = EnvironmentSecretResolver()

    def resolve(self, reference: str) -> str:
        key = reference.strip()
        if key.startswith("managed:"):
            value = self._managed_values.get(key, "")
            if value:
                return value
            raise SecretResolutionError("configured secret is unavailable")
        return self._environment.resolve(key)
