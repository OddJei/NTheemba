"""Per-message runtime context binding for integration-aware ports."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol, runtime_checkable

from ntheemba.domain.business import BusinessIntegration, BusinessProfile
from ntheemba.domain.capabilities import Capability


@runtime_checkable
class BusinessExecutionContext(Protocol):
    """Trusted business execution context used by generic workflows.

    Both a normal business-channel context and an explicitly consumed Marketplace
    handoff satisfy this protocol.  Transport/channel ownership is therefore kept
    separate from the business facts required to execute a workflow safely.
    """

    business: BusinessProfile
    capabilities: frozenset[Capability]
    integrations: tuple[BusinessIntegration, ...]

    def supports(self, capability: Capability) -> bool:
        """Return whether this context enables one canonical business capability."""

    def integration_for(self, capability: Capability) -> BusinessIntegration | None:
        """Return the single active integration for the capability, when unambiguous."""


_RUNTIME_CONTEXT: ContextVar[BusinessExecutionContext | None] = ContextVar(
    "ntheemba_runtime_context",
    default=None,
)


@contextmanager
def bind_runtime_context(
    context: BusinessExecutionContext | None,
) -> Iterator[None]:
    """Bind trusted business execution context for workflow-scoped integration calls."""

    token = _RUNTIME_CONTEXT.set(context)
    try:
        yield
    finally:
        _RUNTIME_CONTEXT.reset(token)


def current_runtime_context() -> BusinessExecutionContext | None:
    """Return the trusted context for the currently routed workflow."""

    return _RUNTIME_CONTEXT.get()
