"""Stable application error types."""

from __future__ import annotations

from typing import Any


class NtheembaError(Exception):
    """Base error that is safe to map to an external response."""

    def __init__(
        self,
        *,
        code: str,
        safe_message: str,
        status_code: int = 500,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}


class ConfigurationError(NtheembaError):
    """Raised when required runtime configuration is invalid."""

    def __init__(self, safe_message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code="CONFIGURATION_ERROR",
            safe_message=safe_message,
            status_code=500,
            retryable=False,
            details=details,
        )


class ServiceUnavailableError(NtheembaError):
    """Raised when a required service is temporarily unavailable."""

    def __init__(
        self,
        safe_message: str = "A required service is temporarily unavailable.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="SERVICE_UNAVAILABLE",
            safe_message=safe_message,
            status_code=503,
            retryable=True,
            details=details,
        )
