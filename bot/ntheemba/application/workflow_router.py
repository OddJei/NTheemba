"""Validated dispatch from interpreted intent to one workflow handler."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol

from ntheemba.application.runtime_context import BusinessExecutionContext, bind_runtime_context
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.enums import IntentType
from ntheemba.domain.intents import Intent
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import TransitionPolicy
from ntheemba.observability.tracer import Tracer
from ntheemba.ports.publisher import ReplyKind


class WorkflowNotRegisteredError(LookupError):
    """Raised when no workflow handler owns an approved intent."""


class WorkflowReplyType(StrEnum):
    """Application-level reply type before gateway command creation."""

    TEXT = "text"
    IMAGE = "image"


@dataclass(frozen=True, slots=True)
class WorkflowReply:
    """Structured workflow reply independent of queue or gateway IDs."""

    kind: WorkflowReplyType
    text: str | None = None
    image_url: str | None = None
    caption: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind == WorkflowReplyType.TEXT:
            if not self.text or not self.text.strip():
                raise ValueError("text replies require text")
            if self.image_url is not None:
                raise ValueError("text replies cannot include image_url")
        if self.kind == WorkflowReplyType.IMAGE:
            if not self.image_url or not self.image_url.strip():
                raise ValueError("image replies require image_url")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def text_reply(
        cls,
        text: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> WorkflowReply:
        """Create a text reply."""

        return cls(
            kind=WorkflowReplyType.TEXT,
            text=text,
            metadata=metadata or {},
        )

    @classmethod
    def image_reply(
        cls,
        image_url: str,
        *,
        caption: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> WorkflowReply:
        """Create an image reply."""

        return cls(
            kind=WorkflowReplyType.IMAGE,
            image_url=image_url,
            caption=caption,
            metadata=metadata or {},
        )

    @property
    def publisher_kind(self) -> ReplyKind:
        """Map the application reply to the publisher command enum."""

        return ReplyKind(self.kind.value)


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    """Structured audit fact emitted by a workflow."""

    event_type: str
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise ValueError("event_type must not be empty")
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """Standard result returned by every workflow handler."""

    replies: tuple[WorkflowReply, ...] = ()
    events: tuple[WorkflowEvent, ...] = ()
    close_session: bool = False


@dataclass(slots=True)
class WorkflowContext:
    """Inputs available to one workflow execution."""

    session: Session
    intent: Intent
    business_id: str
    customer_id: str
    request_id: str
    message_id: str
    capabilities: frozenset[Capability] = frozenset()
    channel_instance_id: str = ""
    business_context: BusinessExecutionContext | None = None
    workflow_origin: str = "business_channel"
    mutation_idempotency_key: str = ""


class WorkflowHandler(Protocol):
    """Handle one or more intent types."""

    async def handle(self, context: WorkflowContext) -> WorkflowResult:
        """Execute workflow logic and mutate only the supplied session."""


class WorkflowRouterPort(Protocol):
    """Route one validated workflow context."""

    async def route(self, context: WorkflowContext) -> WorkflowResult:
        """Return the workflow result for the supplied context."""


class WorkflowRouter:
    """Authorize and dispatch interpreted actions."""

    def __init__(
        self,
        routes: Mapping[IntentType, WorkflowHandler],
        *,
        transition_policy: TransitionPolicy | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self._routes = dict(routes)
        self.transition_policy = transition_policy or TransitionPolicy()
        self.tracer = tracer or Tracer()

    async def route(self, context: WorkflowContext) -> WorkflowResult:
        """Validate the action before invoking its registered workflow."""

        async with self.tracer.span(
            "transition.validate",
            "domain.transition_policy",
            attributes={"intent": context.intent.type.value},
        ):
            self.transition_policy.require_action(
                context.session.transition_context(),
                context.intent.type,
            )
        try:
            handler = self._routes[context.intent.type]
        except KeyError as error:
            raise WorkflowNotRegisteredError(
                f"no workflow is registered for {context.intent.type.value!r}"
            ) from error
        async with self.tracer.span(
            "workflow.execute",
            f"workflows.{type(handler).__name__}",
            attributes={"intent": context.intent.type.value},
        ):
            with bind_runtime_context(context.business_context):
                result = await handler.handle(context)
        if not isinstance(result, WorkflowResult):
            raise TypeError("workflow handlers must return WorkflowResult")
        return result
