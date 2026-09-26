"""Deterministic Ntheemba Marketplace participation, product discovery, and handoff."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from ntheemba.adapters.tradeflow.factory import TradeFlowPortFactory
from ntheemba.adapters.tradeflow.http import TradeFlowIntegrationError
from ntheemba.application.business_workflow_runtime import (
    BusinessWorkflowOrigin,
    BusinessWorkflowRuntime,
)
from ntheemba.domain.business import (
    BusinessProfile,
    ChannelRole,
    ChannelScope,
    ResolvedPlatformContext,
)
from ntheemba.domain.capabilities import Capability, CapabilityCatalogue
from ntheemba.domain.marketplace import (
    MarketplaceBusinessHandoffContext,
    MarketplaceBusinessListing,
    MarketplaceDiscoveryFilter,
    MarketplaceHandoff,
    MarketplaceHandoffStatus,
    MarketplaceListingStatus,
    MarketplaceProductOffer,
    MarketplaceProductSearch,
)
from ntheemba.domain.enums import Flow, IntentType, MessageRole, Stage
from ntheemba.domain.intents import EntitySet, Intent
from ntheemba.domain.product_resolution import ProductQuery, ProductResolution, ResolvedProduct
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import TransitionPolicy
from ntheemba.ports.audit import AuditEvent, AuditSink
from ntheemba.ports.businesses import BusinessRegistry
from ntheemba.ports.marketplace import MarketplaceRegistry, MutableMarketplaceRegistry
from ntheemba.ports.ncpc import NCPCPort
from ntheemba.application.workflow_router import WorkflowResult


PLATFORM_AUDIT_BUSINESS_ID = "__NTHEEMBA_PLATFORM__"


class MarketplaceError(RuntimeError):
    """Base deterministic Marketplace error."""


class MarketplaceAccessError(MarketplaceError):
    """The requested operation is not running inside Marketplace platform context."""


class MarketplaceConfigurationError(MarketplaceError):
    """Marketplace or target-business configuration is unsafe or ambiguous."""


class MarketplaceSelectionError(MarketplaceError):
    """A Marketplace result selection is stale, invalid, or cannot be safely handed off."""


@dataclass(frozen=True, slots=True)
class _MarketplaceOfferDraft:
    business_id: str
    business_name: str
    business_product_id: str
    ncpc_product_id: str
    ncpc_variant_id: str
    name: str
    selling_price: Decimal
    currency: str
    available_quantity: int
    integration_id: str
    business_runtime_revision: int
    shop_id: str
    score: float


def require_marketplace_context(context: object) -> None:
    if (
        not isinstance(context, ResolvedPlatformContext)
        or context.channel.scope is not ChannelScope.PLATFORM
        or context.role is not ChannelRole.MARKETPLACE
    ):
        raise MarketplaceAccessError("Marketplace operations require PLATFORM/MARKETPLACE context")


class MarketplaceControlPlaneService:
    """Configure business Marketplace participation without assigning business capabilities."""

    def __init__(
        self,
        *,
        businesses: BusinessRegistry,
        marketplace: MutableMarketplaceRegistry,
        audit: AuditSink,
    ) -> None:
        self.businesses = businesses
        self.marketplace = marketplace
        self.audit = audit

    async def set_listing(
        self,
        listing: MarketplaceBusinessListing,
        *,
        actor_id: str,
        request_id: str,
    ) -> MarketplaceBusinessListing:
        if not actor_id.strip() or not request_id.strip():
            raise MarketplaceConfigurationError("actor_id and request_id are required")
        business = await self.businesses.get_business(listing.business_id)
        if business is None:
            raise MarketplaceConfigurationError("unknown business")
        if listing.discoverable and not business.enabled:
            raise MarketplaceConfigurationError("disabled businesses cannot be discoverable")
        # Marketplace remains platform policy; this operation never edits declared capabilities.
        await self.marketplace.save_listing(listing)
        await self.audit.record(
            AuditEvent(
                event_type="marketplace.listing_changed",
                request_id=request_id.strip(),
                business_id=PLATFORM_AUDIT_BUSINESS_ID,
                data={
                    "actor_id": actor_id.strip(),
                    "target_business_id": listing.business_id,
                    "status": listing.status.value,
                    "discoverable": listing.discoverable,
                },
            )
        )
        return listing


class MarketplaceDiscoveryService:
    """Resolve businesses eligible for deterministic Marketplace discovery."""

    def __init__(self, *, businesses: BusinessRegistry, marketplace: MarketplaceRegistry) -> None:
        self.businesses = businesses
        self.marketplace = marketplace

    async def eligible_businesses(
        self,
        context: ResolvedPlatformContext,
        *,
        filters: MarketplaceDiscoveryFilter | None = None,
    ) -> tuple[tuple[MarketplaceBusinessListing, BusinessProfile], ...]:
        require_marketplace_context(context)
        selected = filters or MarketplaceDiscoveryFilter()
        results: list[tuple[MarketplaceBusinessListing, BusinessProfile]] = []
        for listing in await self.marketplace.list_listings():
            if not listing.eligible or not _location_matches(listing, selected):
                continue
            business = await self.businesses.get_business(listing.business_id)
            if business is None or not business.enabled:
                continue
            if Capability.PRODUCT_CATALOGUE.value not in business.declared_capabilities:
                continue
            results.append((listing, business))
        return tuple(results)


class MarketplaceProductDiscoveryService:
    """Search trusted NCPC identity across Marketplace-eligible tenant catalogues."""

    def __init__(
        self,
        *,
        businesses: BusinessRegistry,
        marketplace: MarketplaceRegistry,
        ncpc: NCPCPort,
        tradeflow_factory: TradeFlowPortFactory,
    ) -> None:
        self.businesses = businesses
        self.marketplace = marketplace
        self.ncpc = ncpc
        self.tradeflow_factory = tradeflow_factory
        self.discovery = MarketplaceDiscoveryService(
            businesses=businesses,
            marketplace=marketplace,
        )

    async def search(
        self,
        context: ResolvedPlatformContext,
        query: ProductQuery,
        *,
        filters: MarketplaceDiscoveryFilter | None = None,
        ncpc_limit: int = 12,
        result_limit: int = 30,
    ) -> MarketplaceProductSearch:
        require_marketplace_context(context)
        if ncpc_limit <= 0 or result_limit <= 0:
            raise ValueError("search limits must be greater than zero")
        canonical = await self.ncpc.search_products(query, limit=ncpc_limit)
        if not canonical:
            # Cross-business local fallback is deliberately forbidden.
            return MarketplaceProductSearch(
                source_channel_id=context.channel.channel_instance_id,
                query=query,
            )
        variant_order = tuple(
            product.variant_id or product.product_id for product in canonical
        )
        score_by_variant = {
            variant_id: max(0.0, 1.0 - index * 0.05)
            for index, variant_id in enumerate(variant_order)
        }
        raw_offers: list[_MarketplaceOfferDraft] = []
        unavailable: list[str] = []
        eligible = await self.discovery.eligible_businesses(context, filters=filters)
        search_id = f"MPS-{uuid4()}"
        for _listing, business in eligible:
            integrations = await self.businesses.list_integrations(business.business_id)
            integration = _exact_catalogue_integration(integrations)
            if integration is None:
                unavailable.append(business.business_id)
                continue
            try:
                port = self.tradeflow_factory.build(integration)
                products = await port.filter_business_products(
                    business.business_id,
                    variant_order,
                )
            except (TradeFlowIntegrationError, ValueError):
                unavailable.append(business.business_id)
                continue
            for product in products:
                if (
                    not product.public_visible
                    or not product.available
                    or not product.trusted_identity
                    or product.identity_status != "linked"
                    or product.ncpc_product_id is None
                    or product.ncpc_variant_id is None
                    or product.ncpc_variant_id not in score_by_variant
                ):
                    continue
                raw_offers.append(
                    _MarketplaceOfferDraft(
                        business_id=business.business_id,
                        business_name=business.display_name,
                        business_product_id=product.business_product_id,
                        ncpc_product_id=product.ncpc_product_id,
                        ncpc_variant_id=product.ncpc_variant_id,
                        name=product.name,
                        selling_price=product.selling_price,
                        currency=product.currency,
                        available_quantity=product.available_quantity,
                        integration_id=integration.integration_id,
                        business_runtime_revision=business.runtime_revision,
                        shop_id=product.shop_id,
                        score=score_by_variant[product.ncpc_variant_id],
                    )
                )
        raw_offers.sort(
            key=lambda item: (
                -item.score,
                item.selling_price,
                item.business_name.casefold(),
                item.business_product_id,
            )
        )
        finalized = tuple(
            MarketplaceProductOffer(
                result_id=f"{search_id}:{index}",
                business_id=offer.business_id,
                business_name=offer.business_name,
                business_product_id=offer.business_product_id,
                ncpc_product_id=offer.ncpc_product_id,
                ncpc_variant_id=offer.ncpc_variant_id,
                name=offer.name,
                selling_price=offer.selling_price,
                currency=offer.currency,
                available_quantity=offer.available_quantity,
                integration_id=offer.integration_id,
                business_runtime_revision=offer.business_runtime_revision,
                shop_id=offer.shop_id,
                score=offer.score,
            )
            for index, offer in enumerate(raw_offers[:result_limit], start=1)
        )
        return MarketplaceProductSearch(
            source_channel_id=context.channel.channel_instance_id,
            query=query,
            offers=finalized,
            unavailable_business_ids=tuple(sorted(set(unavailable))),
            search_id=search_id,
        )


class MarketplaceHandoffService:
    """Create an explicit, persisted PLATFORM-to-business handoff after result selection."""

    def __init__(
        self,
        *,
        businesses: BusinessRegistry,
        marketplace: MutableMarketplaceRegistry,
        tradeflow_factory: TradeFlowPortFactory,
        catalogue: CapabilityCatalogue | None = None,
        audit: AuditSink | None = None,
    ) -> None:
        self.businesses = businesses
        self.marketplace = marketplace
        self.tradeflow_factory = tradeflow_factory
        self.catalogue = catalogue or CapabilityCatalogue.canonical()
        self.audit = audit

    async def select(
        self,
        context: ResolvedPlatformContext,
        search: MarketplaceProductSearch,
        selection: str | int,
        *,
        now: datetime | None = None,
    ) -> MarketplaceBusinessHandoffContext:
        require_marketplace_context(context)
        if search.source_channel_id != context.channel.channel_instance_id:
            raise MarketplaceSelectionError(
                "Marketplace search belongs to another platform channel"
            )
        if search.is_expired(now=now):
            raise MarketplaceSelectionError("Marketplace search has expired")
        offer = _select_offer(search, selection)
        existing = await self.marketplace.get_handoff_for_result(search.search_id, offer.result_id)
        if existing is not None:
            business = await self.businesses.get_business(existing.target_business_id)
            if business is None or not business.enabled:
                raise MarketplaceSelectionError("selected business is unavailable")
            declaration = self.catalogue.validate_declarations(business.declared_capabilities)
            integrations = await self.businesses.list_integrations(business.business_id)
            return MarketplaceBusinessHandoffContext(
                source_platform_context=context,
                business=business,
                capabilities=declaration.supported,
                integrations=integrations,
                handoff=existing,
            )
        listing = await self.marketplace.get_listing(offer.business_id)
        if listing is None or not listing.eligible:
            raise MarketplaceSelectionError("selected business is no longer Marketplace eligible")
        business = await self.businesses.get_business(offer.business_id)
        if business is None or not business.enabled:
            raise MarketplaceSelectionError("selected business is unavailable")
        declaration = self.catalogue.validate_declarations(business.declared_capabilities)
        if Capability.PRODUCT_CATALOGUE not in declaration.supported:
            raise MarketplaceSelectionError("selected business no longer exposes product catalogue")
        integrations = await self.businesses.list_integrations(business.business_id)
        integration = _exact_catalogue_integration(integrations)
        if integration is None or integration.integration_id != offer.integration_id:
            raise MarketplaceSelectionError("selected business catalogue integration changed")
        try:
            port = self.tradeflow_factory.build(integration)
            current = await port.get_business_product(
                business.business_id,
                offer.business_product_id,
            )
        except (TradeFlowIntegrationError, ValueError) as error:
            raise MarketplaceSelectionError("selected product could not be revalidated") from error
        if (
            current is None
            or not current.public_visible
            or not current.available
            or not current.trusted_identity
            or current.identity_status != "linked"
            or current.ncpc_product_id != offer.ncpc_product_id
            or current.ncpc_variant_id != offer.ncpc_variant_id
        ):
            raise MarketplaceSelectionError("selected product is no longer Marketplace eligible")
        try:
            availability = await port.check_product_availability(
                business.business_id,
                current.business_product_id,
                quantity=1,
                shop_id=offer.shop_id,
            )
        except (TradeFlowIntegrationError, ValueError) as error:
            raise MarketplaceSelectionError(
                "selected shop availability could not be revalidated"
            ) from error
        if not availability.available:
            raise MarketplaceSelectionError("selected product is no longer available")
        if offer.shop_id and availability.shop_id != offer.shop_id:
            raise MarketplaceSelectionError("selected shop changed during Marketplace handoff")
        handoff = MarketplaceHandoff(
            search_id=search.search_id,
            result_id=offer.result_id,
            source_channel_id=context.channel.channel_instance_id,
            target_business_id=business.business_id,
            business_product_id=current.business_product_id,
            ncpc_product_id=current.ncpc_product_id or "",
            ncpc_variant_id=current.ncpc_variant_id or "",
            product_name=current.name,
            selling_price_snapshot=availability.selling_price,
            currency=availability.currency,
            integration_id=integration.integration_id,
            business_runtime_revision=business.runtime_revision,
            shop_id=availability.shop_id or current.shop_id or offer.shop_id,
        )
        await self.marketplace.save_handoff(handoff)
        if self.audit is not None:
            await self.audit.record(
                AuditEvent(
                    event_type="marketplace.handoff_ready",
                    request_id=handoff.handoff_id,
                    business_id=PLATFORM_AUDIT_BUSINESS_ID,
                    data={
                        "target_business_id": handoff.target_business_id,
                        "result_id": handoff.result_id,
                        "business_product_id": handoff.business_product_id,
                        "ncpc_variant_id": handoff.ncpc_variant_id,
                        "shop_id": handoff.shop_id,
                        "integration_id": handoff.integration_id,
                    },
                )
            )
        return MarketplaceBusinessHandoffContext(
            source_platform_context=context,
            business=business,
            capabilities=declaration.supported,
            integrations=integrations,
            handoff=handoff,
        )


class MarketplaceHandoffConsumptionService:
    """Consume a READY Marketplace handoff into a trusted business execution context."""

    def __init__(
        self,
        *,
        businesses: BusinessRegistry,
        marketplace: MutableMarketplaceRegistry,
        tradeflow_factory: TradeFlowPortFactory,
        catalogue: CapabilityCatalogue | None = None,
        audit: AuditSink | None = None,
    ) -> None:
        self.businesses = businesses
        self.marketplace = marketplace
        self.tradeflow_factory = tradeflow_factory
        self.catalogue = catalogue or CapabilityCatalogue.canonical()
        self.audit = audit

    async def consume(
        self,
        context: ResolvedPlatformContext,
        handoff_id: str,
        *,
        now: datetime | None = None,
    ) -> MarketplaceBusinessHandoffContext:
        require_marketplace_context(context)
        handoff = await self.marketplace.get_handoff(handoff_id.strip())
        if handoff is None:
            raise MarketplaceSelectionError("Marketplace handoff is unknown")
        if handoff.source_channel_id != context.channel.channel_instance_id:
            raise MarketplaceSelectionError("Marketplace handoff belongs to another platform channel")
        if handoff.status is MarketplaceHandoffStatus.CANCELLED:
            raise MarketplaceSelectionError("Marketplace handoff was cancelled")

        business = await self.businesses.get_business(handoff.target_business_id)
        if business is None or not business.enabled:
            raise MarketplaceSelectionError("handoff business is unavailable")
        if business.runtime_revision != handoff.business_runtime_revision:
            raise MarketplaceSelectionError("handoff business configuration changed")

        declaration = self.catalogue.validate_declarations(business.declared_capabilities)
        if Capability.PRODUCT_CATALOGUE not in declaration.supported:
            raise MarketplaceSelectionError("handoff business no longer exposes product catalogue")
        integrations = await self.businesses.list_integrations(business.business_id)
        integration = next(
            (
                item
                for item in integrations
                if item.integration_id == handoff.integration_id
                and item.enabled
                and item.status == "active"
                and Capability.PRODUCT_CATALOGUE.value in item.capabilities
            ),
            None,
        )
        if integration is None:
            raise MarketplaceSelectionError("handoff catalogue integration changed")

        if handoff.status is MarketplaceHandoffStatus.READY:
            listing = await self.marketplace.get_listing(business.business_id)
            if listing is None or not listing.eligible:
                raise MarketplaceSelectionError("handoff business is no longer Marketplace eligible")

        try:
            port = self.tradeflow_factory.build(integration)
            current = await port.get_business_product(
                business.business_id,
                handoff.business_product_id,
            )
        except (TradeFlowIntegrationError, ValueError) as error:
            raise MarketplaceSelectionError("handoff product could not be revalidated") from error
        if (
            current is None
            or not current.public_visible
            or not current.available
            or not current.trusted_identity
            or current.identity_status != "linked"
            or current.ncpc_product_id != handoff.ncpc_product_id
            or current.ncpc_variant_id != handoff.ncpc_variant_id
        ):
            raise MarketplaceSelectionError("handoff product is no longer trusted and available")
        try:
            availability = await port.check_product_availability(
                business.business_id,
                current.business_product_id,
                quantity=1,
                shop_id=handoff.shop_id,
            )
        except (TradeFlowIntegrationError, ValueError) as error:
            raise MarketplaceSelectionError("handoff shop could not be revalidated") from error
        if not availability.available:
            raise MarketplaceSelectionError("handoff product is no longer available")
        if handoff.shop_id and availability.shop_id != handoff.shop_id:
            raise MarketplaceSelectionError("handoff shop changed")
        if (
            availability.selling_price != handoff.selling_price_snapshot
            or availability.currency != handoff.currency
        ):
            raise MarketplaceSelectionError("handoff price changed before consumption")

        consumed = handoff
        if handoff.status is MarketplaceHandoffStatus.READY:
            try:
                consumed = await self.marketplace.mark_handoff_consumed(
                    handoff.handoff_id,
                    consumed_at=now or datetime.now(handoff.created_at.tzinfo),
                )
            except (LookupError, ValueError) as error:
                raise MarketplaceSelectionError("Marketplace handoff could not be consumed") from error
            if self.audit is not None:
                await self.audit.record(
                    AuditEvent(
                        event_type="marketplace.handoff_consumed",
                        request_id=consumed.handoff_id,
                        business_id=PLATFORM_AUDIT_BUSINESS_ID,
                        data={
                            "target_business_id": consumed.target_business_id,
                            "business_product_id": consumed.business_product_id,
                            "shop_id": consumed.shop_id,
                            "integration_id": consumed.integration_id,
                        },
                    )
                )
        return MarketplaceBusinessHandoffContext(
            source_platform_context=context,
            business=business,
            capabilities=declaration.supported,
            integrations=integrations,
            handoff=consumed,
        )


@dataclass(slots=True)
class MarketplaceOrderBridgeResult:
    """State and workflow response after entering a selected business order flow."""

    session: Session
    result: WorkflowResult


class MarketplaceOrderBridgeService:
    """Bridge a consumed Marketplace handoff into the normal business order workflow."""

    def __init__(
        self,
        *,
        runtime: BusinessWorkflowRuntime,
        transition_policy: TransitionPolicy | None = None,
    ) -> None:
        self.runtime = runtime
        self.transition_policy = transition_policy or TransitionPolicy()

    async def start_order(
        self,
        context: MarketplaceBusinessHandoffContext,
        *,
        customer_id: str,
        request_id: str,
        message_id: str,
        quantity: int | None = None,
        session: Session | None = None,
    ) -> MarketplaceOrderBridgeResult:
        self._require_consumed_order_context(context)
        active = session or Session.create(
            context.business.business_id,
            customer_id,
            conversation_id=f"MPORDER-{context.handoff.handoff_id}",
        )
        if active.customer_id != customer_id:
            raise MarketplaceSelectionError("Marketplace order session belongs to another customer")
        if active.flow is Flow.IDLE and active.stage is Stage.START:
            selected = ResolvedProduct(
                ncpc_product_id=context.handoff.ncpc_product_id,
                ncpc_variant_id=context.handoff.ncpc_variant_id,
                business_product_id=context.handoff.business_product_id,
                business_id=context.business.business_id,
                name=context.handoff.product_name,
                selling_price=context.handoff.selling_price_snapshot,
                currency=context.handoff.currency,
                available=True,
                shop_id=context.handoff.shop_id,
                identity_status="linked",
                trusted_identity=True,
            )
            active.transition_to(
                self.transition_policy,
                Flow.CATALOGUE,
                Stage.CATALOGUE_SEARCH,
            )
            active.transition_to(
                self.transition_policy,
                Flow.CATALOGUE,
                Stage.PRODUCT_SELECTED,
            )
            active.product_resolution = ProductResolution.resolved(
                ProductQuery(context.handoff.product_name),
                selected,
                confidence=1.0,
            )
        intent = Intent(
            type=IntentType.START_ORDER,
            role=MessageRole.NEW_REQUEST,
            confidence=1.0,
            entities=EntitySet(quantity=quantity, raw_text="marketplace selected product"),
            reasoning_code="marketplace_handoff_order_start",
        )
        result = await self.runtime.route(
            execution_context=context,
            session=active,
            intent=intent,
            request_id=request_id,
            message_id=message_id,
            origin=BusinessWorkflowOrigin.MARKETPLACE_HANDOFF,
            channel_instance_id=context.source_platform_context.channel.channel_instance_id,
            mutation_idempotency_key=f"MPORDER:{context.handoff.handoff_id}",
        )
        return MarketplaceOrderBridgeResult(active, result)

    async def continue_order(
        self,
        context: MarketplaceBusinessHandoffContext,
        session: Session,
        intent: Intent,
        *,
        request_id: str,
        message_id: str,
    ) -> WorkflowResult:
        self._require_consumed_order_context(context)
        return await self.runtime.route(
            execution_context=context,
            session=session,
            intent=intent,
            request_id=request_id,
            message_id=message_id,
            origin=BusinessWorkflowOrigin.MARKETPLACE_HANDOFF,
            channel_instance_id=context.source_platform_context.channel.channel_instance_id,
            mutation_idempotency_key=f"MPORDER:{context.handoff.handoff_id}",
        )

    @staticmethod
    def _require_consumed_order_context(context: MarketplaceBusinessHandoffContext) -> None:
        if context.handoff.status is not MarketplaceHandoffStatus.CONSUMED:
            raise MarketplaceSelectionError("Marketplace order requires a consumed handoff")
        if Capability.PRODUCT_ORDER not in context.capabilities:
            raise MarketplaceSelectionError("selected business has not enabled product ordering")


def _location_matches(
    listing: MarketplaceBusinessListing,
    selected: MarketplaceDiscoveryFilter,
) -> bool:
    for listing_value, requested in (
        (listing.province_id, selected.province_id),
        (listing.district_id, selected.district_id),
        (listing.town_id, selected.town_id),
    ):
        if requested and listing_value != requested:
            return False
    if selected.area_text:
        return selected.area_text.strip().casefold() in listing.area_text.strip().casefold()
    return True


def _exact_catalogue_integration(integrations):
    matches = tuple(
        item
        for item in integrations
        if item.enabled
        and item.status == "active"
        and Capability.PRODUCT_CATALOGUE.value in item.capabilities
    )
    return matches[0] if len(matches) == 1 else None


def _select_offer(
    search: MarketplaceProductSearch,
    selection: str | int,
) -> MarketplaceProductOffer:
    if isinstance(selection, int):
        index = selection - 1
        if index < 0 or index >= len(search.offers):
            raise MarketplaceSelectionError("Marketplace selection number is out of range")
        return search.offers[index]
    value = selection.strip()
    if not value:
        raise MarketplaceSelectionError("Marketplace selection must not be empty")
    if value.isdigit():
        return _select_offer(search, int(value))
    matches = [offer for offer in search.offers if offer.result_id == value]
    if len(matches) != 1:
        raise MarketplaceSelectionError("Marketplace result ID is unknown")
    return matches[0]
