"""Developer-only controls for deterministic fake dependency behavior."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ntheemba.devtools.fake_dependencies import (
    FakeDependencyBehavior,
    FakeDependencyController,
    FakeDependencyFailure,
)

router = APIRouter(
    prefix="/dev/dependencies",
    tags=["developer-dependencies"],
    include_in_schema=False,
)


class FakeDependencyBehaviorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dependency: str
    latency_ms: int
    fail_next: int
    always_fail: bool
    failure_message: str
    operations: tuple[str, ...]


class ConfigureFakeDependencyRequest(BaseModel):
    latency_ms: Annotated[int, Field(ge=0, le=30_000)] = 0
    fail_next: Annotated[int, Field(ge=0, le=100)] = 0
    always_fail: bool = False
    failure_message: Annotated[str, Field(min_length=1, max_length=200)] = (
        "Injected fake dependency failure"
    )
    operations: Annotated[list[str], Field(max_length=20)] = []


class ProbeFakeDependencyRequest(BaseModel):
    operation: Annotated[str, Field(min_length=1, max_length=80)] = "probe"


class ProbeFakeDependencyResponse(BaseModel):
    dependency: str
    operation: str
    status: str


def _controller(request: Request) -> FakeDependencyController:
    controller = getattr(request.app.state, "fake_dependency_controller", None)
    if not isinstance(controller, FakeDependencyController):
        raise HTTPException(status_code=503, detail="Fake dependency controller unavailable")
    return controller


def _behavior_response(
    behavior: FakeDependencyBehavior,
) -> FakeDependencyBehaviorResponse:
    return FakeDependencyBehaviorResponse.model_validate(behavior)


def _not_found(error: KeyError) -> HTTPException:
    dependency = str(error.args[0]) if error.args else "unknown"
    return HTTPException(status_code=404, detail=f"Unknown fake dependency: {dependency}")


@router.get("", response_model=list[FakeDependencyBehaviorResponse])
async def list_fake_dependencies(request: Request) -> list[FakeDependencyBehaviorResponse]:
    behaviors = await _controller(request).list_behaviors()
    return [_behavior_response(behavior) for behavior in behaviors]


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_all_fake_dependencies(request: Request) -> Response:
    await _controller(request).reset_all()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{dependency}", response_model=FakeDependencyBehaviorResponse)
async def get_fake_dependency(
    dependency: str,
    request: Request,
) -> FakeDependencyBehaviorResponse:
    try:
        behavior = await _controller(request).get_behavior(dependency)
    except KeyError as error:
        raise _not_found(error) from error
    return _behavior_response(behavior)


@router.put("/{dependency}", response_model=FakeDependencyBehaviorResponse)
async def configure_fake_dependency(
    dependency: str,
    payload: ConfigureFakeDependencyRequest,
    request: Request,
) -> FakeDependencyBehaviorResponse:
    try:
        behavior = await _controller(request).configure(
            dependency,
            latency_ms=payload.latency_ms,
            fail_next=payload.fail_next,
            always_fail=payload.always_fail,
            failure_message=payload.failure_message,
            operations=payload.operations,
        )
    except KeyError as error:
        raise _not_found(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _behavior_response(behavior)


@router.delete("/{dependency}", response_model=FakeDependencyBehaviorResponse)
async def reset_fake_dependency(
    dependency: str,
    request: Request,
) -> FakeDependencyBehaviorResponse:
    try:
        behavior = await _controller(request).reset(dependency)
    except KeyError as error:
        raise _not_found(error) from error
    return _behavior_response(behavior)


@router.post("/{dependency}/probe", response_model=ProbeFakeDependencyResponse)
async def probe_fake_dependency(
    dependency: str,
    payload: ProbeFakeDependencyRequest,
    request: Request,
) -> ProbeFakeDependencyResponse:
    controller = _controller(request)
    try:
        await controller.before_call(dependency, payload.operation)
    except KeyError as error:
        raise _not_found(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except FakeDependencyFailure as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "FAKE_DEPENDENCY_FAILURE",
                "dependency": error.dependency,
                "operation": error.operation,
                "message": str(error),
            },
        ) from error
    return ProbeFakeDependencyResponse(
        dependency=dependency.strip().lower().replace("-", "_"),
        operation=payload.operation.strip().lower(),
        status="passed",
    )
