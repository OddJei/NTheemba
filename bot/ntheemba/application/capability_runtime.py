"""Business resolution and canonical capability enforcement."""

from __future__ import annotations

from dataclasses import dataclass

from ntheemba.application.runtime_profiles import RuntimeProfileCompiler
from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowEvent,
    WorkflowReply,
    WorkflowResult,
    WorkflowRouter,
)
from ntheemba.domain.business import (
    ChannelScope,
    ResolvedBusinessContext,
    ResolvedPlatformContext,
)
from ntheemba.domain.capabilities import Capability, CapabilityCatalogue
from ntheemba.domain.enums import Flow, FulfilmentMethod, IntentType, ItemType
from ntheemba.domain.gateway import InboundGatewayMessage
from ntheemba.observability.tracer import Tracer
from ntheemba.ports.businesses import (
    BusinessRegistry,
    UnsupportedDeclarationKind,
    UnsupportedDeclarationObservation,
    UnsupportedDeclarationSink,
)


class UnknownBusinessChannelError(LookupError):
    """Raised when no active business owns an inbound channel."""


class BusinessUnavailableError(LookupError):
    """Raised when a configured business is missing or disabled."""


@dataclass(frozen=True, slots=True)
class CapabilityDecision:
    """Required and missing capabilities for one workflow action."""

    required: frozenset[Capability]
    missing: frozenset[Capability]

    @property
    def allowed(self) -> bool:
        return not self.missing


class BusinessContextResolver:
    """Resolve channels and validate business declarations against Ntheemba."""

    def __init__(
        self,
        *,
        registry: BusinessRegistry,
        catalogue: CapabilityCatalogue,
        observations: UnsupportedDeclarationSink,
        profile_compiler: RuntimeProfileCompiler | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self.registry = registry
        self.catalogue = catalogue
        self.observations = observations
        self.profile_compiler = profile_compiler
        self.tracer = tracer or Tracer()

    async def resolve(self, message: InboundGatewayMessage) -> ResolvedBusinessContext:
        """Resolve an exact channel before any message interpretation."""

        async with self.tracer.span(
            "business.resolve",
            "application.business_context",
            attributes={"channel_instance_id": message.channel_instance_id},
        ):
            channel = await self.registry.get_channel_by_identity(
                message.provider, message.channel_instance_id, message.recipient_phone
            )
            if channel is None or not channel.enabled:
                raise UnknownBusinessChannelError(message.channel_instance_id)
            if channel.scope is not ChannelScope.BUSINESS or channel.business_id is None:
                raise UnknownBusinessChannelError(
                    f"channel {message.channel_instance_id!r} is not a business channel"
                )
            business = await self.registry.get_business(channel.business_id)
            if business is None or not business.enabled:
                raise BusinessUnavailableError(channel.business_id)
            if self.profile_compiler is not None:
                profile = await self.profile_compiler.compile(business, channel)
                for value in sorted(profile.rejected_declarations):
                    await self.observations.record(
                        UnsupportedDeclarationObservation.now(
                            kind=UnsupportedDeclarationKind.CAPABILITY,
                            value=value,
                            business_id=business.business_id,
                            adapter_type=business.adapter_type,
                            source="business_declaration",
                        )
                    )
                return profile.context_for()

        async with self.tracer.span(
            "capabilities.load",
            "domain.capability_catalogue",
            attributes={"business_id": business.business_id},
        ):
            declaration = self.catalogue.validate_declarations(
                business.declared_capabilities
            )
            for value in sorted(declaration.unknown):
                await self.observations.record(
                    UnsupportedDeclarationObservation.now(
                        kind=UnsupportedDeclarationKind.CAPABILITY,
                        value=value,
                        business_id=business.business_id,
                        adapter_type=business.adapter_type,
                        source="business_declaration",
                    )
                )

        return ResolvedBusinessContext(
            business=business,
            channel=channel,
            capabilities=declaration.supported,
            rejected_declarations=declaration.unknown,
            integrations=await self.registry.list_integrations(business.business_id),
        )


class ChannelContextResolver:
    """Resolve an exact external channel to business or platform context.

    Platform contexts never enter business capability compilation, which prevents
    Marketplace from inheriting a business or TradeFlow integration accidentally.
    """

    def __init__(self, *, registry: BusinessRegistry, business_resolver: BusinessContextResolver) -> None:
        self.registry = registry
        self.business_resolver = business_resolver

    async def resolve(
        self, message: InboundGatewayMessage
    ) -> ResolvedBusinessContext | ResolvedPlatformContext:
        channel = await self.registry.get_channel_by_identity(
            message.provider, message.channel_instance_id, message.recipient_phone
        )
        if channel is None or not channel.enabled:
            raise UnknownBusinessChannelError(message.channel_instance_id)
        if channel.scope is ChannelScope.PLATFORM:
            return ResolvedPlatformContext(
                channel=channel,
                role=channel.role,
                capabilities=channel.platform_capabilities,
            )
        return await self.business_resolver.resolve(message)


class CapabilityRequirementPolicy:
    """Map workflow actions to canonical Ntheemba capabilities."""

    def requirements(self, context: WorkflowContext) -> frozenset[Capability]:
        intent = context.intent.type
        flow = context.session.flow

        direct: dict[IntentType, frozenset[Capability]] = {
            IntentType.BUSINESS_INFO: frozenset({Capability.BUSINESS_INFORMATION}),
            IntentType.BUSINESS_HOURS: frozenset({Capability.BUSINESS_HOURS}),
            IntentType.FAQ: frozenset({Capability.FAQ}),
            IntentType.HANDOVER: frozenset({Capability.HANDOVER}),
            IntentType.LOYALTY_STATUS: frozenset({Capability.LOYALTY_READ}),
        }
        if intent in direct:
            return direct[intent]

        if intent == IntentType.START_BOOKING or flow == Flow.BOOKING:
            return frozenset(
                {Capability.SERVICE_CATALOGUE, Capability.APPOINTMENT_CREATE}
            )

        if intent == IntentType.START_ORDER or flow == Flow.ORDER:
            required = {Capability.PRODUCT_CATALOGUE, Capability.PRODUCT_ORDER}
            method = context.intent.entities.fulfilment_method
            draft = context.session.order_draft
            if method is None and draft is not None:
                method = draft.fulfilment_method
            if method == FulfilmentMethod.DELIVERY:
                required.add(Capability.DELIVERY)
            elif method == FulfilmentMethod.COLLECTION:
                required.add(Capability.COLLECTION)
            return frozenset(required)

        if intent in {IntentType.CATALOGUE_SEARCH, IntentType.SELECT_ITEM}:
            if (
                context.intent.entities.item_type == ItemType.SERVICE
                or context.session.flow == Flow.BOOKING
            ):
                return frozenset({Capability.SERVICE_CATALOGUE})
            return frozenset({Capability.PRODUCT_CATALOGUE})

        return frozenset()

    def decide(self, context: WorkflowContext) -> CapabilityDecision:
        required = self.requirements(context)
        missing = required.difference(context.capabilities)
        return CapabilityDecision(required, frozenset(missing))


class CapabilityAwareWorkflowRouter:
    """Guard the existing router without embedding business-specific logic."""

    def __init__(
        self,
        inner: WorkflowRouter,
        *,
        policy: CapabilityRequirementPolicy | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self.inner = inner
        self.policy = policy or CapabilityRequirementPolicy()
        self.tracer = tracer or inner.tracer

    async def route(self, context: WorkflowContext) -> WorkflowResult:
        async with self.tracer.span(
            "capabilities.validate",
            "application.capability_guard",
            attributes={"intent": context.intent.type.value},
        ):
            decision = self.policy.decide(context)
        if not decision.allowed:
            missing = ", ".join(sorted(item.value for item in decision.missing))
            return WorkflowResult(
                replies=(
                    WorkflowReply.text_reply(
                        "This business has not enabled that option yet. "
                        "You can ask about its currently available products, services, "
                        "orders, bookings, or request a person."
                    ),
                ),
                events=(
                    WorkflowEvent(
                        "capability.denied",
                        {
                            "missing": tuple(
                                sorted(item.value for item in decision.missing)
                            ),
                            "required": tuple(
                                sorted(item.value for item in decision.required)
                            ),
                            "summary": missing,
                        },
                    ),
                ),
            )
        return await self.inner.route(context)
