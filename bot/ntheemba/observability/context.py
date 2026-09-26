"""Trace context creation and propagation."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class TraceContext:
    """Correlation data propagated through one message execution."""

    trace_id: str
    span_id: str
    parent_span_id: str = ""
    request_id: str = ""
    business_id: str = ""
    conversation_id: str = ""
    message_id: str = ""
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in {"trace_id": self.trace_id, "span_id": self.span_id}.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))

    def child(self, *, attributes: Mapping[str, Any] | None = None) -> TraceContext:
        """Create a child span that keeps the current correlation identifiers."""

        merged_attributes = dict(self.attributes)
        if attributes is not None:
            merged_attributes.update(attributes)
        return TraceContext(
            trace_id=self.trace_id,
            span_id=_new_span_id(),
            parent_span_id=self.span_id,
            request_id=self.request_id,
            business_id=self.business_id,
            conversation_id=self.conversation_id,
            message_id=self.message_id,
            attributes=merged_attributes,
        )


_CURRENT_TRACE_CONTEXT: ContextVar[TraceContext | None] = ContextVar(
    "ntheemba_trace_context", default=None
)


def _new_trace_id() -> str:
    return f"TRACE-{uuid4()}"


def _new_span_id() -> str:
    return f"SPAN-{uuid4()}"


def new_trace_context(
    *,
    request_id: str = "",
    business_id: str = "",
    conversation_id: str = "",
    message_id: str = "",
    attributes: Mapping[str, Any] | None = None,
) -> TraceContext:
    """Create a root context for one incoming message execution."""

    return TraceContext(
        trace_id=_new_trace_id(),
        span_id=_new_span_id(),
        request_id=request_id,
        business_id=business_id,
        conversation_id=conversation_id,
        message_id=message_id,
        attributes=attributes or {},
    )


def current_trace_context() -> TraceContext | None:
    """Return the context bound to the current asynchronous execution."""

    return _CURRENT_TRACE_CONTEXT.get()


def set_trace_context(context: TraceContext) -> Token[TraceContext | None]:
    """Bind a context and return the token needed to restore the previous one."""

    return _CURRENT_TRACE_CONTEXT.set(context)


def reset_trace_context(token: Token[TraceContext | None]) -> None:
    """Restore the context that existed before ``set_trace_context``."""

    _CURRENT_TRACE_CONTEXT.reset(token)


@contextmanager
def bind_trace_context(context: TraceContext) -> Iterator[TraceContext]:
    """Temporarily bind a trace context to the current execution."""

    token = set_trace_context(context)
    try:
        yield context
    finally:
        reset_trace_context(token)
