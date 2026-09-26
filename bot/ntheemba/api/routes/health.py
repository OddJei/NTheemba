"""Liveness and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from ntheemba.api.schemas import HealthResponse, ReadinessCheck, ReadinessResponse
from ntheemba.config import Settings
from ntheemba.observability.runtime import ObservabilityRuntime

router = APIRouter(tags=["system"])


def _settings_from_request(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        raise RuntimeError("Application settings were not initialized")
    return settings


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Check service liveness",
)
async def health(request: Request) -> HealthResponse:
    """Report whether the FastAPI process is alive."""

    settings = _settings_from_request(request)
    return HealthResponse(
        service=settings.app_name,
        version=settings.version,
        environment=settings.environment,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Check service readiness",
)
async def readiness(request: Request) -> ReadinessResponse:
    """Report application and observability composition readiness."""

    checks = {
        "application": ReadinessCheck(
            status="ready",
            detail="FastAPI application initialized",
        )
    }
    runtime = getattr(request.app.state, "observability_runtime", None)
    if not isinstance(runtime, ObservabilityRuntime):
        checks["observability"] = ReadinessCheck(
            status="not_ready",
            detail="Observability runtime was not initialized",
        )
    else:
        snapshot = await runtime.snapshot()
        if snapshot.enabled and snapshot.sink_count == 0:
            checks["observability"] = ReadinessCheck(
                status="not_ready",
                detail="Tracing is enabled but no trace sink is configured",
            )
        elif not snapshot.enabled:
            checks["observability"] = ReadinessCheck(
                status="ready",
                detail="Tracing is explicitly disabled",
            )
        else:
            checks["observability"] = ReadinessCheck(
                status="ready",
                detail=(
                    f"{snapshot.sink_count} trace sink(s) configured; "
                    f"{snapshot.emission_failures} emission failure(s)"
                ),
            )

    storage = getattr(request.app.state, "storage_runtime", None)
    if storage is None:
        checks["storage"] = ReadinessCheck(
            status="not_ready", detail="Storage runtime was not initialized"
        )
    else:
        snapshot = await storage.snapshot()
        storage_ready = snapshot.opened and snapshot.redis_ready and snapshot.postgres_ready
        checks["storage"] = ReadinessCheck(
            status="ready" if storage_ready else "not_ready",
            detail=snapshot.detail,
        )

    overall = "ready" if all(check.status == "ready" for check in checks.values()) else "not_ready"
    return ReadinessResponse(status=overall, checks=checks)
