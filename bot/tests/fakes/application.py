"""Application-level fakes for interpreter and workflow tests."""

from __future__ import annotations

from collections.abc import Callable

from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowResult,
)
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.intents import Intent
from ntheemba.domain.session import Session


class StubInterpreter:
    """Return a configured intent or injected exception."""

    def __init__(self, result: Intent | Exception) -> None:
        self.result = result
        self.calls: list[tuple[str, str, frozenset[Capability]]] = []

    async def interpret(
        self,
        text: str,
        session: Session,
        *,
        capabilities: frozenset[Capability] = frozenset(),
    ) -> Intent:
        self.calls.append((text, session.conversation_id, capabilities))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class RecordingWorkflowHandler:
    """Record contexts, optionally mutate sessions, and return a result."""

    def __init__(
        self,
        result: WorkflowResult | Exception,
        *,
        mutation: Callable[[WorkflowContext], None] | None = None,
    ) -> None:
        self.result = result
        self.mutation = mutation
        self.calls: list[WorkflowContext] = []

    async def handle(self, context: WorkflowContext) -> WorkflowResult:
        self.calls.append(context)
        if self.mutation is not None:
            self.mutation(context)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result
