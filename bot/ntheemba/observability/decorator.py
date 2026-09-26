"""Decorator for tracing asynchronous application methods."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

from ntheemba.observability.tracer import Tracer

P = ParamSpec("P")
R = TypeVar("R")


def trace_node(
    node_id: str,
    component: str,
    *,
    tracer_attribute: str = "_tracer",
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Trace an async method using a ``Tracer`` stored on its first argument."""

    if not node_id.strip():
        raise ValueError("node_id must not be empty")
    if not component.strip():
        raise ValueError("component must not be empty")
    if not tracer_attribute.strip():
        raise ValueError("tracer_attribute must not be empty")

    def decorator(function: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(function)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if not args:
                raise RuntimeError("trace_node requires a bound method")
            owner = cast(Any, args[0])
            tracer = getattr(owner, tracer_attribute, None)
            if not isinstance(tracer, Tracer):
                raise RuntimeError(
                    f"{type(owner).__name__}.{tracer_attribute} must contain a Tracer"
                )
            async with tracer.span(node_id, component):
                return await function(*args, **kwargs)

        return wrapper

    return decorator
