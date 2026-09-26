"""Secret-reference resolution without persisting secret values in tenant configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Protocol


class SecretResolutionError(LookupError):
    """Raised when a configured secret reference cannot be resolved safely."""


class SecretResolver(Protocol):
    """Resolve an opaque configuration reference into a runtime-only secret value."""

    def resolve(self, reference: str) -> str: ...


class EnvironmentSecretResolver:
    """Resolve only explicit ``env:VARIABLE`` references from process environment."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = os.environ if environ is None else environ

    def resolve(self, reference: str) -> str:
        prefix, separator, name = reference.strip().partition(":")
        if separator != ":" or prefix.casefold() != "env" or not name.strip():
            raise SecretResolutionError("unsupported secret reference")
        value = self._environ.get(name.strip(), "")
        if not value:
            raise SecretResolutionError("configured secret is unavailable")
        return value


class StaticSecretResolver:
    """Deterministic reference resolver for tests and local composition."""

    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)

    def resolve(self, reference: str) -> str:
        try:
            value = self._values[reference]
        except KeyError as error:
            raise SecretResolutionError("configured secret is unavailable") from error
        if not value:
            raise SecretResolutionError("configured secret is unavailable")
        return value
