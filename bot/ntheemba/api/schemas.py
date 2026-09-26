"""HTTP response schemas used by the FastAPI boundary."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictResponseModel(BaseModel):
    """Base response model that rejects undeclared fields."""

    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictResponseModel):
    """Liveness response."""

    status: Literal["ok"] = "ok"
    service: str
    version: str
    environment: str


class ReadinessCheck(StrictResponseModel):
    """One readiness dependency check."""

    status: Literal["ready", "not_ready"]
    detail: str | None = None


class ReadinessResponse(StrictResponseModel):
    """Service readiness response."""

    status: Literal["ready", "not_ready"]
    checks: dict[str, ReadinessCheck] = Field(default_factory=dict)


class ErrorBody(StrictResponseModel):
    """Stable public error body."""

    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(StrictResponseModel):
    """Stable public error envelope."""

    error: ErrorBody
