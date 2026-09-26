"""Deterministic retry/dead-letter classification for worker failures."""

from __future__ import annotations

from enum import StrEnum

from ntheemba.application.capability_runtime import (
    BusinessUnavailableError,
    UnknownBusinessChannelError,
)
from ntheemba.infrastructure.errors import NtheembaError


class FailureDisposition(StrEnum):
    """Worker action required for a failed delivery."""

    RETRY = "retry"
    DEAD_LETTER = "dead_letter"


def classify_failure(error: Exception) -> FailureDisposition:
    """Classify safe deterministic failures before falling back to bounded retry."""

    if isinstance(error, (UnknownBusinessChannelError, BusinessUnavailableError, ValueError)):
        return FailureDisposition.DEAD_LETTER
    if isinstance(error, NtheembaError):
        return (
            FailureDisposition.RETRY
            if error.retryable
            else FailureDisposition.DEAD_LETTER
        )

    retryable = getattr(error, "retryable", None)
    if retryable is True:
        return FailureDisposition.RETRY
    if retryable is False:
        return FailureDisposition.DEAD_LETTER

    if isinstance(error, (TimeoutError, ConnectionError)):
        return FailureDisposition.RETRY

    # Unknown failures are retried only within the worker's bounded attempt policy.
    return FailureDisposition.RETRY
