"""Developer-only, in-memory conversation simulator composition."""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from copy import copy
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

from ntheemba.adapters.businesses import (
    InMemoryBusinessRegistry,
    InMemoryUnsupportedDeclarationSink,
)
from ntheemba.adapters.businesses.seeds import reference_integrations
from ntheemba.adapters.customers import InMemoryCustomerDirectory
from ntheemba.adapters.tradeflow import DynamicTradeFlowPort
from ntheemba.application.capability_runtime import (
    BusinessContextResolver,
    CapabilityAwareWorkflowRouter,
)
from ntheemba.application.customer_bridge import CustomerBridgeService
from ntheemba.application.customer_workflow import CustomerAwareWorkflowHandler
from ntheemba.application.gateway_service import GatewayMessageService
from ntheemba.application.service import (
    NtheembaService,
    ProcessMessageCommand,
    ProcessMessageOutcome,
)
from ntheemba.application.session_coordinator import SessionCoordinator
from ntheemba.application.workflow_router import (
    WorkflowContext,
    WorkflowHandler,
    WorkflowResult,
    WorkflowRouter,
)
from ntheemba.domain.booking_draft import AppointmentSlot, ServiceSelection
from ntheemba.domain.business import (
    BusinessChannel,
    BusinessProfile,
    ResolvedBusinessContext,
)
from ntheemba.domain.capabilities import (
    Capability,
    CapabilityCatalogue,
    CapabilityDefinition,
)
from ntheemba.domain.customers import (
    LoyaltyStatus,
    MinimalBusinessClient,
    PlatformCustomer,
    normalize_phone_e164,
)
from ntheemba.domain.enums import Flow, IntentType
from ntheemba.domain.gateway import InboundGatewayMessage
from ntheemba.domain.intents import Intent
from ntheemba.domain.product_resolution import ProductQuery
from ntheemba.domain.session import Session
from ntheemba.observability.events import TraceEvent
from ntheemba.observability.tracer import Tracer
from ntheemba.ports.audit import AuditEvent
from ntheemba.ports.businesses import UnsupportedDeclarationObservation
from ntheemba.ports.ncpc import CanonicalProduct
from ntheemba.ports.publisher import OutgoingMessage
from ntheemba.ports.sessions import DeduplicationKey, SessionConflictError, SessionKey
from ntheemba.ports.tradeflow import (
    BookingSubmissionRequest,
    BusinessHours,
    BusinessInformation,
    BusinessProduct,
    FAQAnswer,
    MinimalClientCreateRequest,
    OrderSubmissionRequest,
    ProductAvailability,
    StaffOption,
    SubmissionResult,
)
from ntheemba.services.interpretation import HybridInterpreter
from ntheemba.services.product_resolver import ProductResolver
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.booking import BookingWorkflow
from ntheemba.workflows.catalogue import CatalogueWorkflow
from ntheemba.workflows.handover import HandoverWorkflow
from ntheemba.workflows.information import InformationWorkflow
from ntheemba.workflows.loyalty import LoyaltyWorkflow
from ntheemba.workflows.order import OrderWorkflow

from .fake_dependencies import FakeDependencyController


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _clone_session(session: Session) -> Session:
    cloned = copy(session)
    cloned.order_draft = copy(session.order_draft) if session.order_draft else None
    cloned.booking_draft = copy(session.booking_draft) if session.booking_draft else None
    cloned.recent_history = list(session.recent_history)
    return cloned


def _tokens(value: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", value.lower()))


@dataclass(frozen=True, slots=True)
class SimulatorBusiness:
    """One selectable developer business profile."""

    business_id: str
    name: str
    description: str
    suggested_messages: tuple[str, ...]
    group: str = "standard"
    adapter_type: str = "tradeflow_standard"
    channel_instance_id: str = ""
    phone_e164: str = ""
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SimulatorConversation:
    """Seeded conversation card in the multi-business workspace."""

    conversation_id: str
    business_id: str
    channel_instance_id: str
    customer_phone: str
    customer_name: str
    title: str
    scenario_group: str
    status: str
    suggested_messages: tuple[str, ...]
    latest_message: str = ""


@dataclass(frozen=True, slots=True)
class SimulatorReply:
    """Customer-visible outgoing message captured from the real publisher port."""

    message_id: str
    kind: str
    text: str
    image_url: str
    caption: str


@dataclass(frozen=True, slots=True)
class SimulatorSessionSnapshot:
    """Safe session state exposed to the developer UI."""

    exists: bool
    conversation_id: str = ""
    business_id: str = ""
    customer_id: str = ""
    flow: str = "idle"
    stage: str = "start"
    mode: str = "bot"
    status: str = "active"
    handover_status: str = "none"
    revision: int = 0
    pending_prompt: str = ""
    selected_product: str = ""
    quantity: int | None = None
    fulfilment_method: str = ""
    selected_service: str = ""
    selected_date: str = ""
    selected_time: str = ""
    selected_staff: str = ""
    customer_name: str = ""
    contact_number: str = ""
    submitted_request_id: str = ""
    history: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class SimulatorMessageResult:
    """Complete result of one simulated inbound message."""

    outcome: ProcessMessageOutcome
    trace_id: str
    replies: tuple[SimulatorReply, ...]
    session: SimulatorSessionSnapshot


class ControlledInterpreter:
    """Apply developer dependency controls around the real interpreter."""

    def __init__(self, controller: FakeDependencyController) -> None:
        self._controller = controller
        self._inner = HybridInterpreter()

    async def interpret(
        self,
        text: str,
        session: Session,
        *,
        capabilities: frozenset[Capability] = frozenset(),
    ) -> Intent:
        await self._controller.before_call("interpreter", "interpret")
        return await self._inner.interpret(text, session, capabilities=capabilities)


class SimulatorAuditSink:
    """In-memory audit sink controlled by Phase 11.6 fault injection."""

    def __init__(self, controller: FakeDependencyController) -> None:
        self._controller = controller
        self.events: list[AuditEvent] = []

    async def record(self, event: AuditEvent) -> None:
        await self._controller.before_call("audit", "record")
        self.events.append(event)

    async def record_many(self, events: tuple[AuditEvent, ...]) -> None:
        for event in events:
            await self.record(event)


class SimulatorOutgoingPublisher:
    """Capture outgoing messages while preserving the real publisher boundary."""

    def __init__(self, controller: FakeDependencyController) -> None:
        self._controller = controller
        self.messages: list[OutgoingMessage] = []

    async def publish(self, message: OutgoingMessage) -> None:
        await self._controller.before_call("publisher", "publish")
        self.messages.append(message)

    async def publish_many(self, messages: tuple[OutgoingMessage, ...]) -> None:
        await self._controller.before_call("publisher", "publish_many")
        self.messages.extend(messages)


class SimulatorSessionRepository:
    """Revision-aware, controllable session repository for the simulator."""

    def __init__(self, controller: FakeDependencyController) -> None:
        self._controller = controller
        self._sessions: dict[str, Session] = {}
        self.archived: list[Session] = []

    async def load(self, key: SessionKey) -> Session | None:
        await self._controller.before_call("session_repository", "load")
        session = self._sessions.get(key.value)
        return _clone_session(session) if session is not None else None

    async def save(
        self,
        session: Session,
        *,
        expected_revision: int | None,
    ) -> Session:
        await self._controller.before_call("session_repository", "save")
        key = SessionKey(session.business_id, session.customer_id)
        current = self._sessions.get(key.value)
        if current is None:
            if expected_revision is not None:
                raise SessionConflictError("cannot update a missing session")
            next_revision = 1
        else:
            if expected_revision != current.revision:
                raise SessionConflictError(
                    f"expected revision {expected_revision}, found {current.revision}"
                )
            next_revision = current.revision + 1
        saved = _clone_session(session)
        saved.revision = next_revision
        self._sessions[key.value] = _clone_session(saved)
        return _clone_session(saved)

    async def delete(self, key: SessionKey) -> None:
        await self._controller.before_call("session_repository", "delete")
        self._sessions.pop(key.value, None)

    async def archive(self, session: Session) -> None:
        await self._controller.before_call("session_repository", "archive")
        self.archived.append(_clone_session(session))

    async def peek(self, key: SessionKey) -> Session | None:
        session = self._sessions.get(key.value)
        return _clone_session(session) if session is not None else None

    async def force_delete(self, key: SessionKey) -> Session | None:
        session = self._sessions.pop(key.value, None)
        return _clone_session(session) if session is not None else None


class SimulatorSessionLockManager:
    """Per-conversation locks with deterministic fault controls."""

    def __init__(self, controller: FakeDependencyController) -> None:
        self._controller = controller
        self._locks: dict[str, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    async def _get_lock(self, key: SessionKey) -> asyncio.Lock:
        async with self._guard:
            return self._locks.setdefault(key.value, asyncio.Lock())

    @asynccontextmanager
    async def lock(
        self,
        key: SessionKey,
        *,
        acquire_timeout: float | None = None,
    ) -> AsyncIterator[None]:
        await self._controller.before_call("session_lock", "lock")
        lock = await self._get_lock(key)
        if acquire_timeout is None:
            await lock.acquire()
        else:
            await asyncio.wait_for(lock.acquire(), timeout=acquire_timeout)
        try:
            yield
        finally:
            lock.release()


class SimulatorDeduplicationStore:
    """Atomic in-memory message claims with reset support."""

    def __init__(
        self,
        controller: FakeDependencyController,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._controller = controller
        self._clock = clock
        self._claims: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def claim(self, key: DeduplicationKey, *, ttl: timedelta) -> bool:
        await self._controller.before_call("deduplication", "claim")
        if ttl <= timedelta(0):
            raise ValueError("ttl must be greater than zero")
        now = self._clock()
        async with self._lock:
            for value in [value for value, expires_at in self._claims.items() if expires_at <= now]:
                del self._claims[value]
            if key.value in self._claims:
                return False
            self._claims[key.value] = now + ttl
            return True

    async def release(self, key: DeduplicationKey) -> None:
        await self._controller.before_call("deduplication", "release")
        async with self._lock:
            self._claims.pop(key.value, None)

    async def force_release_many(self, business_id: str, message_ids: set[str]) -> None:
        async with self._lock:
            for message_id in message_ids:
                self._claims.pop(DeduplicationKey(business_id, message_id).value, None)


class SimulatorNCPC:
    """Seeded NCPC implementation controlled by fake dependency plans."""

    def __init__(
        self,
        controller: FakeDependencyController,
        products: tuple[CanonicalProduct, ...],
    ) -> None:
        self._controller = controller
        self.products = {product.product_id: product for product in products}

    async def search_products(
        self,
        query: ProductQuery,
        *,
        limit: int = 20,
    ) -> tuple[CanonicalProduct, ...]:
        await self._controller.before_call("ncpc", "search_products")
        query_tokens = _tokens(
            " ".join(
                value
                for value in (
                    query.original_text,
                    query.brand or "",
                    query.product_family or "",
                    query.variant or "",
                    query.category or "",
                )
                if value
            )
        )
        scored: list[tuple[int, CanonicalProduct]] = []
        for product in self.products.values():
            searchable = " ".join(
                value
                for value in (
                    product.canonical_name,
                    product.brand or "",
                    product.product_family or "",
                    product.variant or "",
                    product.category or "",
                    *product.aliases,
                )
                if value
            )
            score = len(query_tokens & _tokens(searchable))
            if not query_tokens or score:
                scored.append((score, product))
        scored.sort(key=lambda item: (-item[0], item[1].canonical_name.lower()))
        return tuple(product for _, product in scored[:limit])

    async def get_product(self, product_id: str) -> CanonicalProduct | None:
        await self._controller.before_call("ncpc", "get_product")
        return self.products.get(product_id)

    async def resolve_barcode(self, barcode: str) -> CanonicalProduct | None:
        await self._controller.before_call("ncpc", "resolve_barcode")
        return next(
            (product for product in self.products.values() if product.barcode == barcode.strip()),
            None,
        )


class SimulatorTradeFlow:
    """Seeded TradeFlow implementation for real workflow execution."""

    def __init__(self, controller: FakeDependencyController) -> None:
        self._controller = controller
        self.businesses: dict[str, BusinessInformation] = {}
        self.faqs: dict[str, tuple[FAQAnswer, ...]] = {}
        self.products: dict[str, dict[str, BusinessProduct]] = {}
        self.services: dict[str, dict[str, ServiceSelection]] = {}
        self.clients: dict[str, dict[str, MinimalBusinessClient]] = {}
        self.loyalty: dict[str, LoyaltyStatus] = {}
        self.client_creations: dict[str, MinimalBusinessClient] = {}
        self.orders: dict[str, SubmissionResult] = {}
        self.bookings: dict[str, SubmissionResult] = {}

    async def _before(self, operation: str) -> None:
        await self._controller.before_call("tradeflow", operation)

    async def get_business_information(self, business_id: str) -> BusinessInformation:
        await self._before("get_business_information")
        return self.businesses[business_id]

    async def get_business_hours(self, business_id: str, *, at: datetime) -> BusinessHours:
        await self._before("get_business_hours")
        opens_at = time(8, 0)
        closes_at = time(18, 0)
        local_time = at.timetz().replace(tzinfo=None)
        return BusinessHours(
            is_open=opens_at <= local_time < closes_at,
            local_date=at.date(),
            opens_at=opens_at,
            closes_at=closes_at,
            note="Developer simulator schedule.",
        )

    async def search_faqs(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 5,
    ) -> tuple[FAQAnswer, ...]:
        await self._before("search_faqs")
        terms = _tokens(query)
        matches = [
            answer
            for answer in self.faqs.get(business_id, ())
            if not terms or terms & _tokens(f"{answer.question} {answer.answer}")
        ]
        return tuple(sorted(matches, key=lambda item: -item.score)[:limit])

    async def filter_business_products(
        self,
        business_id: str,
        ncpc_variant_ids: tuple[str, ...],
    ) -> tuple[BusinessProduct, ...]:
        await self._before("filter_business_products")
        wanted = set(ncpc_variant_ids)
        return tuple(
            product
            for product in self.products.get(business_id, {}).values()
            if product.ncpc_variant_id in wanted and product.public_visible
        )

    async def search_business_products(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 12,
    ) -> tuple[BusinessProduct, ...]:
        await self._before("search_business_products")
        terms = tuple(token for token in query.lower().split() if token)
        matches = [
            product
            for product in self.products.get(business_id, {}).values()
            if product.public_visible
            and (
                not terms
                or all(
                    token in f"{product.name} {product.barcode or ''}".lower()
                    for token in terms
                )
            )
        ]
        return tuple(sorted(matches, key=lambda item: item.name.lower())[:limit])

    async def get_business_product(
        self,
        business_id: str,
        business_product_id: str,
    ) -> BusinessProduct | None:
        await self._before("get_business_product")
        return self.products.get(business_id, {}).get(business_product_id)

    async def search_services(
        self,
        business_id: str,
        query: str,
        *,
        limit: int = 20,
    ) -> tuple[ServiceSelection, ...]:
        await self._before("search_services")
        normalized = query.strip().lower()
        services = tuple(self.services.get(business_id, {}).values())
        matches = [
            service
            for service in services
            if not normalized
            or normalized in service.name.lower()
            or any(token in service.name.lower() for token in _tokens(normalized))
        ]
        return tuple(sorted(matches, key=lambda item: item.name.lower())[:limit])

    async def get_service(self, business_id: str, service_id: str) -> ServiceSelection | None:
        await self._before("get_service")
        return self.services.get(business_id, {}).get(service_id)

    async def find_client_by_phone(
        self,
        business_id: str,
        phone_e164: str,
    ) -> MinimalBusinessClient | None:
        await self._before("find_client_by_phone")
        return self.clients.get(business_id, {}).get(phone_e164)

    async def create_minimal_client(
        self,
        business_id: str,
        request: MinimalClientCreateRequest,
        *,
        idempotency_key: str,
    ) -> MinimalBusinessClient:
        await self._before("create_minimal_client")
        existing = self.client_creations.get(idempotency_key)
        if existing is not None:
            return existing
        client = MinimalBusinessClient(
            client_id=f"CLIENT-{uuid4()}",
            display_name=request.display_name.strip(),
            phone_e164=request.phone_e164,
        )
        self.clients.setdefault(business_id, {})[request.phone_e164] = client
        self.client_creations[idempotency_key] = client
        return client

    async def get_loyalty_status(
        self,
        business_id: str,
        client_id: str,
    ) -> LoyaltyStatus | None:
        await self._before("get_loyalty_status")
        del business_id
        return self.loyalty.get(client_id)

    async def check_product_availability(
        self,
        business_id: str,
        business_product_id: str,
        *,
        quantity: int,
        shop_id: str = "",
    ) -> ProductAvailability:
        await self._before("check_product_availability")
        product = self.products[business_id][business_product_id]
        return ProductAvailability(
            business_product_id=product.business_product_id,
            requested_quantity=quantity,
            available_quantity=product.available_quantity,
            selling_price=product.selling_price,
            currency=product.currency,
            public_visible=product.public_visible,
            shop_id=shop_id or product.shop_id,
        )

    async def get_available_slots(
        self,
        business_id: str,
        service_id: str,
        *,
        appointment_date: date,
    ) -> tuple[AppointmentSlot, ...]:
        await self._before("get_available_slots")
        if service_id not in self.services.get(business_id, {}):
            return ()
        return (
            AppointmentSlot(
                slot_id=f"{service_id}-{appointment_date.isoformat()}-0900",
                service_id=service_id,
                appointment_date=appointment_date,
                start_time=time(9, 0),
                end_time=time(10, 30),
            ),
            AppointmentSlot(
                slot_id=f"{service_id}-{appointment_date.isoformat()}-1400",
                service_id=service_id,
                appointment_date=appointment_date,
                start_time=time(14, 0),
                end_time=time(15, 30),
            ),
        )

    async def get_qualified_staff(
        self,
        business_id: str,
        service_id: str,
        *,
        appointment_date: date,
        start_time: time,
    ) -> tuple[StaffOption, ...]:
        await self._before("get_qualified_staff")
        del appointment_date, start_time
        if service_id not in self.services.get(business_id, {}):
            return ()
        return (StaffOption("staff-serah", "Serah"), StaffOption("staff-mary", "Mary"))

    async def create_order_request(
        self,
        business_id: str,
        request: OrderSubmissionRequest,
        *,
        idempotency_key: str,
    ) -> SubmissionResult:
        await self._before("create_order_request")
        del business_id, request
        existing = self.orders.get(idempotency_key)
        if existing is not None:
            return SubmissionResult(existing.request_id, existing.status, False)
        result = SubmissionResult(
            request_id=f"ORD-{uuid4()}",
            status="pending_business_confirmation",
            created=True,
        )
        self.orders[idempotency_key] = result
        return result

    async def create_booking_request(
        self,
        business_id: str,
        request: BookingSubmissionRequest,
        *,
        idempotency_key: str,
    ) -> SubmissionResult:
        await self._before("create_booking_request")
        del business_id, request
        existing = self.bookings.get(idempotency_key)
        if existing is not None:
            return SubmissionResult(existing.request_id, existing.status, False)
        result = SubmissionResult(
            request_id=f"BKG-{uuid4()}",
            status="pending_business_confirmation",
            created=True,
        )
        self.bookings[idempotency_key] = result
        return result


class FlowAwareWorkflowHandler:
    """Dispatch ambiguous intent types according to the current session flow."""

    def __init__(
        self,
        *,
        information: WorkflowHandler,
        catalogue: WorkflowHandler,
        order: WorkflowHandler,
        booking: WorkflowHandler,
        loyalty: WorkflowHandler,
        handover: WorkflowHandler,
        responses: ResponseBuilder,
    ) -> None:
        self._information = information
        self._catalogue = catalogue
        self._order = order
        self._booking = booking
        self._loyalty = loyalty
        self._handover = handover
        self._responses = responses

    async def handle(self, context: WorkflowContext) -> WorkflowResult:
        intent_type = context.intent.type
        if intent_type in {IntentType.BUSINESS_INFO, IntentType.BUSINESS_HOURS, IntentType.FAQ}:
            return await self._information.handle(context)
        if intent_type in {IntentType.HANDOVER, IntentType.RESUME_BOT, IntentType.CLOSE_SESSION}:
            return await self._handover.handle(context)
        if intent_type == IntentType.LOYALTY_STATUS:
            return await self._loyalty.handle(context)
        if intent_type == IntentType.START_BOOKING or context.session.flow == Flow.BOOKING:
            return await self._booking.handle(context)
        if intent_type == IntentType.START_ORDER or context.session.flow == Flow.ORDER:
            return await self._order.handle(context)
        if intent_type in {IntentType.CATALOGUE_SEARCH, IntentType.SELECT_ITEM}:
            return await self._catalogue.handle(context)
        if intent_type in {IntentType.CLARIFY, IntentType.UNKNOWN, IntentType.CONTINUE}:
            return WorkflowResult(
                replies=(
                    self._responses.clarification(
                        "Tell me what you would like to know, buy, book, or check about loyalty."
                    ),
                )
            )
        if intent_type in {
            IntentType.PROVIDE_QUANTITY,
            IntentType.PROVIDE_FULFILMENT_METHOD,
            IntentType.PROVIDE_DELIVERY_DETAILS,
            IntentType.PROVIDE_CUSTOMER_DETAILS,
            IntentType.CONFIRM,
            IntentType.CORRECT,
            IntentType.CANCEL,
        }:
            return await self._order.handle(context)
        raise LookupError(f"simulator has no workflow for {intent_type.value}")


class DeveloperConversationSimulator:
    """Drive the real application pipeline with developer-only in-memory adapters."""

    def __init__(
        self,
        *,
        controller: FakeDependencyController,
        tracer: Tracer,
        trace_events: Callable[[], Awaitable[tuple[TraceEvent, ...]]],
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._controller = controller
        self._clock = clock
        self._trace_events = trace_events
        self._repository = SimulatorSessionRepository(controller)
        self._locks = SimulatorSessionLockManager(controller)
        self._deduplication = SimulatorDeduplicationStore(controller, clock=clock)
        self._publisher = SimulatorOutgoingPublisher(controller)
        self._audit = SimulatorAuditSink(controller)
        self._ncpc = SimulatorNCPC(controller, _seed_canonical_products())
        self._tradeflow = SimulatorTradeFlow(controller)
        self._businesses = _seed_tradeflow(self._tradeflow, clock())
        (
            profiles,
            channels,
            self._workspace_businesses,
            self._workspace_conversations,
        ) = _seed_business_runtime(self._businesses, clock())
        self._business_profiles = {
            profile.business_id: profile for profile in profiles
        }
        self._business_channels = {
            channel.business_id: channel for channel in channels
        }
        self._business_integrations = reference_integrations()
        self._capability_catalogue = CapabilityCatalogue.canonical()
        self._business_registry = InMemoryBusinessRegistry(
            businesses=profiles,
            channels=channels,
            integrations=self._business_integrations,
        )
        self._unsupported_observations = InMemoryUnsupportedDeclarationSink()
        self._customer_directory = InMemoryCustomerDirectory()
        self._customer_bridge = CustomerBridgeService(
            customers=self._customer_directory,
            clients=self._tradeflow,
        )
        self._business_contexts = BusinessContextResolver(
            registry=self._business_registry,
            catalogue=self._capability_catalogue,
            observations=self._unsupported_observations,
            tracer=tracer,
        )
        self._message_ids: dict[str, set[str]] = {}
        self._last_commands: dict[str, ProcessMessageCommand] = {}
        self._workspace_session_keys: dict[str, SessionKey] = {}
        self._workspace_last_messages: dict[str, str] = {}

        responses = ResponseBuilder()
        dynamic_tradeflow = DynamicTradeFlowPort(
            {
                "tradeflow_standard": self._tradeflow,
                "tradeflow_serahs": self._tradeflow,
            }
        )
        resolver = ProductResolver(ncpc=self._ncpc, tradeflow=dynamic_tradeflow)
        catalogue = CatalogueWorkflow(
            resolver=resolver,
            tradeflow=dynamic_tradeflow,
            responses=responses,
        )
        order = OrderWorkflow(
            catalogue=catalogue,
            tradeflow=dynamic_tradeflow,
            responses=responses,
        )
        booking = BookingWorkflow(
            tradeflow=dynamic_tradeflow,
            responses=responses,
            clock=clock,
        )
        information = InformationWorkflow(
            tradeflow=dynamic_tradeflow,
            responses=responses,
            clock=clock,
        )
        loyalty = LoyaltyWorkflow(
            customers=self._customer_bridge,
            tradeflow=dynamic_tradeflow,
        )
        handover = HandoverWorkflow(responses=responses)
        flow_dispatcher = FlowAwareWorkflowHandler(
            information=information,
            catalogue=catalogue,
            order=order,
            booking=booking,
            loyalty=loyalty,
            handover=handover,
            responses=responses,
        )
        dispatcher: WorkflowHandler = CustomerAwareWorkflowHandler(
            flow_dispatcher,
            customers=self._customer_bridge,
        )
        routes = {intent_type: dispatcher for intent_type in IntentType}
        base_router = WorkflowRouter(routes, tracer=tracer)
        router = CapabilityAwareWorkflowRouter(base_router, tracer=tracer)
        coordinator = SessionCoordinator(
            self._repository,
            self._locks,
            clock=clock,
            ttl=timedelta(hours=24),
        )
        self._service = NtheembaService(
            coordinator=coordinator,
            deduplication=self._deduplication,
            interpreter=ControlledInterpreter(controller),
            router=router,
            publisher=self._publisher,
            audit=self._audit,
            clock=clock,
            tracer=tracer,
        )
        self._gateway_service = GatewayMessageService(
            businesses=self._business_contexts,
            customers=self._customer_bridge,
            core=self._service,
            tracer=tracer,
        )

    @property
    def businesses(self) -> tuple[SimulatorBusiness, ...]:
        return self._businesses

    @property
    def workspace_businesses(self) -> tuple[SimulatorBusiness, ...]:
        """Return all business/channel profiles used by the multi-conversation UI."""

        return self._workspace_businesses

    @property
    def canonical_capabilities(self) -> tuple[CapabilityDefinition, ...]:
        """Return Ntheemba's closed capability catalogue for diagnostics."""

        return tuple(
            self._capability_catalogue.definitions[capability]
            for capability in sorted(
                self._capability_catalogue.definitions,
                key=lambda item: item.value,
            )
        )

    @property
    def workspace_conversations(self) -> tuple[SimulatorConversation, ...]:
        """Return seeded conversations with their latest simulated message."""

        return tuple(
            replace(
                conversation,
                latest_message=self._workspace_last_messages.get(
                    conversation.conversation_id,
                    conversation.latest_message,
                ),
            )
            for conversation in self._workspace_conversations
        )

    async def unsupported_observations(
        self,
    ) -> tuple[UnsupportedDeclarationObservation, ...]:
        """Return unknown capability/operation observations for developer review."""

        return await self._unsupported_observations.list_observations()

    async def send_workspace_message(
        self,
        conversation_id: str,
        text: str,
        *,
        message_id: str | None = None,
        request_id: str | None = None,
    ) -> SimulatorMessageResult:
        """Route a message from its receiving channel through the full Phase 11.20 path."""

        conversation = next(
            (
                item
                for item in self._workspace_conversations
                if item.conversation_id == conversation_id
            ),
            None,
        )
        if conversation is None:
            raise KeyError(conversation_id)
        channel = await self._business_registry.get_channel(
            conversation.channel_instance_id
        )
        if channel is None:
            raise KeyError(conversation.channel_instance_id)
        resolved_message_id = message_id or f"SIM-{uuid4()}"
        resolved_request_id = request_id or f"REQ-SIM-{uuid4()}"
        before_count = len(self._publisher.messages)
        routed = await self._gateway_service.process(
            InboundGatewayMessage(
                request_id=resolved_request_id,
                message_id=resolved_message_id,
                channel_instance_id=conversation.channel_instance_id,
                provider=channel.provider,
                recipient_phone=channel.phone_e164,
                customer_phone=conversation.customer_phone,
                text=text,
                received_at=self._clock(),
                metadata={"simulator_conversation_id": conversation_id},
            )
        )
        key = SessionKey(
            routed.business.business.business_id,
            routed.customer.customer_id,
        )
        self._workspace_session_keys[conversation_id] = key
        self._workspace_last_messages[conversation_id] = text
        self._message_ids.setdefault(key.value, set()).add(resolved_message_id)
        published = self._publisher.messages[before_count:]
        replies = tuple(_reply_snapshot(message) for message in published)
        session = await self._repository.peek(key)
        trace_id = await self._trace_id_for_request(routed.outcome.request_id)
        return SimulatorMessageResult(
            outcome=routed.outcome,
            trace_id=trace_id,
            replies=replies,
            session=_session_snapshot(session),
        )

    async def get_workspace_session(
        self,
        conversation_id: str,
    ) -> SimulatorSessionSnapshot:
        key = self._workspace_session_keys.get(conversation_id)
        if key is None:
            return SimulatorSessionSnapshot(exists=False)
        return _session_snapshot(await self._repository.peek(key))

    async def reset_workspace_conversation(self, conversation_id: str) -> None:
        key = self._workspace_session_keys.pop(conversation_id, None)
        if key is None:
            self._workspace_last_messages.pop(conversation_id, None)
            return
        await self._repository.force_delete(key)
        message_ids = self._message_ids.pop(key.value, set())
        await self._deduplication.force_release_many(key.business_id, message_ids)
        self._workspace_last_messages.pop(conversation_id, None)

    async def send_message(self, command: ProcessMessageCommand) -> SimulatorMessageResult:
        if command.business_id not in {business.business_id for business in self._businesses}:
            raise KeyError(command.business_id)
        command = self._with_business_capabilities(command)
        key = SessionKey(command.business_id, command.customer_id)
        key_value = key.value
        before_count = len(self._publisher.messages)
        self._message_ids.setdefault(key_value, set()).add(command.message_id)
        self._last_commands[key_value] = command
        self._ensure_classic_customer(command)
        outcome = await self._service.process_message(command)
        published = self._publisher.messages[before_count:]
        replies = tuple(_reply_snapshot(message) for message in published)
        session = await self._repository.peek(key)
        trace_id = await self._trace_id_for_request(outcome.request_id)
        return SimulatorMessageResult(
            outcome=outcome,
            trace_id=trace_id,
            replies=replies,
            session=_session_snapshot(session),
        )

    async def replay_last(
        self,
        business_id: str,
        customer_id: str,
        *,
        same_message_id: bool,
    ) -> SimulatorMessageResult:
        key = SessionKey(business_id, customer_id)
        previous = self._last_commands.get(key.value)
        if previous is None:
            raise LookupError("No previous simulator message exists")
        command = ProcessMessageCommand(
            business_id=previous.business_id,
            customer_id=previous.customer_id,
            message_id=previous.message_id if same_message_id else f"SIM-{uuid4()}",
            text=previous.text,
            whatsapp_session_id=previous.whatsapp_session_id,
            channel_instance_id=previous.channel_instance_id,
            customer_phone=previous.customer_phone,
            enabled_capabilities=previous.enabled_capabilities,
            business_context=previous.business_context,
            request_id=f"REQ-SIM-{uuid4()}",
            received_at=self._clock(),
        )
        return await self.send_message(command)

    def _with_business_capabilities(
        self,
        command: ProcessMessageCommand,
    ) -> ProcessMessageCommand:
        if command.enabled_capabilities and command.business_context is not None:
            return command
        profile = self._business_profiles.get(command.business_id)
        if profile is None:
            return command
        capabilities = command.enabled_capabilities or frozenset(
            Capability(capability)
            for capability in profile.declared_capabilities
        )
        return ProcessMessageCommand(
            business_id=command.business_id,
            customer_id=command.customer_id,
            message_id=command.message_id,
            text=command.text,
            whatsapp_session_id=command.whatsapp_session_id,
            channel_instance_id=command.channel_instance_id,
            customer_phone=command.customer_phone,
            enabled_capabilities=capabilities,
            business_context=self._business_context_for(profile),
            request_id=command.request_id,
            received_at=command.received_at,
        )

    def _business_context_for(
        self,
        profile: BusinessProfile,
    ) -> ResolvedBusinessContext | None:
        channel = self._business_channels.get(profile.business_id)
        if channel is None:
            return None
        declaration = self._capability_catalogue.validate_declarations(
            profile.declared_capabilities
        )
        integrations = tuple(
            integration
            for integration in self._business_integrations
            if integration.business_id == profile.business_id
        )
        return ResolvedBusinessContext(
            business=profile,
            channel=channel,
            capabilities=declaration.supported,
            rejected_declarations=declaration.unknown,
            integrations=integrations,
            runtime_revision=profile.runtime_revision,
        )

    def _ensure_classic_customer(self, command: ProcessMessageCommand) -> None:
        if command.customer_id in self._customer_directory._customers:
            return
        phone = normalize_phone_e164(command.customer_phone or command.customer_id)
        customer = PlatformCustomer(
            customer_id=command.customer_id,
            phone_e164=phone,
            created_at=self._clock(),
            last_seen_at=self._clock(),
        )
        self._customer_directory._customers[customer.customer_id] = customer
        self._customer_directory._customer_by_phone[customer.phone_e164] = (
            customer.customer_id
        )

    async def get_session(self, business_id: str, customer_id: str) -> SimulatorSessionSnapshot:
        return _session_snapshot(await self._repository.peek(SessionKey(business_id, customer_id)))

    async def reset_conversation(self, business_id: str, customer_id: str) -> None:
        key = SessionKey(business_id, customer_id)
        await self._repository.force_delete(key)
        message_ids = self._message_ids.pop(key.value, set())
        await self._deduplication.force_release_many(business_id, message_ids)
        self._last_commands.pop(key.value, None)

    async def expire_conversation(self, business_id: str, customer_id: str) -> None:
        key = SessionKey(business_id, customer_id)
        session = await self._repository.force_delete(key)
        if session is not None:
            session.expires_at = self._clock()
            session.expire(now=self._clock())
            self._repository.archived.append(session)

    async def audit_events(self) -> tuple[AuditEvent, ...]:
        """Return the simulator's safe in-memory audit trail in emission order."""

        return tuple(self._audit.events)

    async def trace_for_request(self, request_id: str) -> tuple[TraceEvent, ...]:
        events = await self._all_trace_events()
        return tuple(event for event in events if event.request_id == request_id)

    async def _trace_id_for_request(self, request_id: str) -> str:
        events = await self.trace_for_request(request_id)
        return events[0].trace_id if events else ""

    async def _all_trace_events(self) -> tuple[TraceEvent, ...]:
        return await self._trace_events()


def _reply_snapshot(message: OutgoingMessage) -> SimulatorReply:
    return SimulatorReply(
        message_id=message.message_id,
        kind=message.kind.value,
        text=message.text or "",
        image_url=message.image_url or "",
        caption=message.caption or "",
    )


def _session_snapshot(session: Session | None) -> SimulatorSessionSnapshot:
    if session is None:
        return SimulatorSessionSnapshot(exists=False)
    order = session.order_draft
    booking = session.booking_draft
    pending_prompt = session.pending_question.prompt if session.pending_question else ""
    selected_product = ""
    quantity: int | None = None
    fulfilment = ""
    selected_service = ""
    selected_date = ""
    selected_time = ""
    selected_staff = ""
    customer_name = ""
    contact_number = ""
    submitted_request_id = ""
    if order is not None:
        selected_product = order.product.name if order.product else ""
        quantity = order.quantity
        fulfilment = order.fulfilment_method.value if order.fulfilment_method else ""
        customer_name = order.customer_name or ""
        contact_number = order.contact_number or ""
        submitted_request_id = order.submitted_request_id or ""
    if booking is not None:
        selected_service = booking.service.name if booking.service else ""
        selected_date = booking.preferred_date.isoformat() if booking.preferred_date else ""
        selected_time = (
            booking.selected_slot.start_time.strftime("%H:%M") if booking.selected_slot else ""
        )
        selected_staff = booking.preferred_staff_name or ""
        customer_name = booking.customer_name or customer_name
        contact_number = booking.contact_number or contact_number
        submitted_request_id = booking.submitted_request_id or submitted_request_id
    history = tuple(
        {
            "role": turn.role,
            "text": turn.text,
            "message_id": turn.message_id,
            "at": turn.at.isoformat(),
        }
        for turn in session.recent_history
    )
    return SimulatorSessionSnapshot(
        exists=True,
        conversation_id=session.conversation_id,
        business_id=session.business_id,
        customer_id=session.customer_id,
        flow=session.flow.value,
        stage=session.stage.value,
        mode=session.mode.value,
        status=session.status.value,
        handover_status=session.handover_status.value,
        revision=session.revision,
        pending_prompt=pending_prompt,
        selected_product=selected_product,
        quantity=quantity,
        fulfilment_method=fulfilment,
        selected_service=selected_service,
        selected_date=selected_date,
        selected_time=selected_time,
        selected_staff=selected_staff,
        customer_name=customer_name,
        contact_number=contact_number,
        submitted_request_id=submitted_request_id,
        history=history,
    )


def _seed_canonical_products() -> tuple[CanonicalProduct, ...]:
    return (
        CanonicalProduct(
            "ncpc-oil-2l",
            "Pure Drop Cooking Oil 2L",
            brand="Pure Drop",
            product_family="cooking oil",
            variant="2L",
            size_value=Decimal("2"),
            size_unit="l",
            barcode="6001000000001",
            category="groceries",
            aliases=("oil", "cooking oil", "vegetable oil"),
        ),
        CanonicalProduct(
            "ncpc-oil-5l",
            "Pure Drop Cooking Oil 5L",
            brand="Pure Drop",
            product_family="cooking oil",
            variant="5L",
            size_value=Decimal("5"),
            size_unit="l",
            barcode="6001000000002",
            category="groceries",
            aliases=("oil", "cooking oil", "vegetable oil"),
        ),
        CanonicalProduct(
            "ncpc-coke-500ml",
            "Coca-Cola 500ml",
            brand="Coca-Cola",
            product_family="soft drink",
            variant="500ml",
            size_value=Decimal("500"),
            size_unit="ml",
            barcode="6001000000003",
            category="beverages",
            aliases=("coke", "cola", "drink"),
        ),
        CanonicalProduct(
            "ncpc-mealie-25kg",
            "Breakfast Mealie Meal 25kg",
            brand="Breakfast",
            product_family="mealie meal",
            variant="25kg",
            size_value=Decimal("25"),
            size_unit="kg",
            barcode="6001000000004",
            category="groceries",
            aliases=("meal meal", "mealie meal", "breakfast"),
        ),
        CanonicalProduct(
            "ncpc-expression-black",
            "Expression Braiding Hair Black",
            brand="Expression",
            product_family="braiding hair",
            variant="black",
            barcode="6001000000005",
            category="hair and beauty",
            aliases=("hair", "braiding hair", "expression", "black hair"),
        ),
        CanonicalProduct(
            "ncpc-bob-wig-black",
            "Black Bob Wig",
            brand="Glow Collection",
            product_family="wig",
            variant="black bob",
            barcode="6001000000006",
            category="hair and beauty",
            aliases=("wig", "black wig", "bob wig"),
        ),
    )


def _seed_tradeflow(
    tradeflow: SimulatorTradeFlow,
    now: datetime,
) -> tuple[SimulatorBusiness, ...]:
    tomorrow = (now + timedelta(days=1)).date().isoformat()
    harvest = BusinessInformation(
        business_id="harvest-big-shop",
        name="Harvest Big Shop",
        description="A neighbourhood grocery and household shop.",
        location="Mufulira, Copperbelt",
        contact_phone="+260970000001",
    )
    amac = BusinessInformation(
        business_id="amac-enterprise",
        name="AMAC Enterprise",
        description="A small retail shop using the standard TradeFlow edition.",
        location="Mufulira, Copperbelt",
        contact_phone="+260970000002",
    )
    serahs = BusinessInformation(
        business_id="serahs-glow-lounge",
        name="Serah's Glow Lounge",
        description="Hair, beauty, products, appointments, clients and loyalty.",
        location="Kalukanya at Alpha Rock School, Mufulira",
        contact_phone="+260976078440",
    )
    tradeflow.businesses = {
        harvest.business_id: harvest,
        amac.business_id: amac,
        serahs.business_id: serahs,
    }
    tradeflow.faqs = {
        harvest.business_id: (
            FAQAnswer(
                "faq-delivery",
                "Do you deliver?",
                "Yes. Delivery is available in selected Mufulira areas.",
            ),
            FAQAnswer("faq-payment", "How can I pay?", "You can pay using cash or mobile money."),
        ),
        amac.business_id: (
            FAQAnswer(
                "faq-collection",
                "Can I collect?",
                "Yes. Orders can be collected after the shop confirms them.",
            ),
        ),
        serahs.business_id: (
            FAQAnswer(
                "faq-walkin",
                "Do you accept walk-ins?",
                "Walk-ins are welcome when a stylist is available.",
            ),
            FAQAnswer(
                "faq-deposit",
                "Do bookings need a deposit?",
                "Some longer services may require a deposit after confirmation.",
            ),
        ),
    }
    harvest_products = (
        BusinessProduct(
            "harvest-oil-2l",
            "ncpc-oil-2l",
            "Pure Drop Cooking Oil 2L",
            Decimal("95"),
            "ZMW",
            18,
        ),
        BusinessProduct(
            "harvest-oil-5l",
            "ncpc-oil-5l",
            "Pure Drop Cooking Oil 5L",
            Decimal("225"),
            "ZMW",
            8,
        ),
        BusinessProduct(
            "harvest-coke-500ml",
            "ncpc-coke-500ml",
            "Coca-Cola 500ml",
            Decimal("15"),
            "ZMW",
            40,
        ),
        BusinessProduct(
            "harvest-mealie-25kg",
            "ncpc-mealie-25kg",
            "Breakfast Mealie Meal 25kg",
            Decimal("245"),
            "ZMW",
            12,
        ),
    )
    amac_products = (
        BusinessProduct(
            "amac-coke-500ml",
            "ncpc-coke-500ml",
            "Coca-Cola 500ml",
            Decimal("16"),
            "ZMW",
            16,
        ),
        BusinessProduct(
            "amac-oil-2l",
            "ncpc-oil-2l",
            "Pure Drop Cooking Oil 2L",
            Decimal("98"),
            "ZMW",
            5,
        ),
    )
    serah_products = (
        BusinessProduct(
            "serah-expression-black",
            "ncpc-expression-black",
            "Expression Braiding Hair Black",
            Decimal("75"),
            "ZMW",
            20,
        ),
        BusinessProduct(
            "serah-bob-wig-black",
            "ncpc-bob-wig-black",
            "Black Bob Wig",
            Decimal("650"),
            "ZMW",
            3,
        ),
    )
    tradeflow.products[harvest.business_id] = {
        product.business_product_id: product for product in harvest_products
    }
    tradeflow.products[amac.business_id] = {
        product.business_product_id: product for product in amac_products
    }
    tradeflow.products[serahs.business_id] = {
        product.business_product_id: product for product in serah_products
    }
    services = (
        ServiceSelection("service-knotless", "Knotless Braids", 180, Decimal("350"), "ZMW"),
        ServiceSelection("service-makeup", "Makeup Session", 60, Decimal("250"), "ZMW"),
        ServiceSelection("service-nails", "Gel Nails", 90, Decimal("180"), "ZMW"),
    )
    tradeflow.services[serahs.business_id] = {
        service.service_id: service for service in services
    }
    tradeflow.services[harvest.business_id] = {}
    tradeflow.services[amac.business_id] = {}

    natasha = MinimalBusinessClient(
        client_id="SGL-CLIENT-0001",
        display_name="Natasha",
        phone_e164="+260970000101",
    )
    ruth = MinimalBusinessClient(
        client_id="SGL-CLIENT-0002",
        display_name="Ruth",
        phone_e164="+260970000777",
    )
    tradeflow.clients[serahs.business_id] = {
        natasha.phone_e164: natasha,
        ruth.phone_e164: ruth,
    }
    tradeflow.clients[harvest.business_id] = {}
    tradeflow.clients[amac.business_id] = {}
    tradeflow.loyalty[natasha.client_id] = LoyaltyStatus(
        client_id=natasha.client_id,
        tier="Silver",
        points=Decimal("82"),
        next_tier="Gold",
        points_needed=Decimal("38"),
        reward_description="Your current reward applies to eligible salon services.",
        discount_percent=Decimal("15"),
        discount_scope="eligible services",
    )
    tradeflow.loyalty[ruth.client_id] = LoyaltyStatus(
        client_id=ruth.client_id,
        tier="Bronze",
        points=Decimal("46"),
        next_tier="Silver",
        points_needed=Decimal("34"),
        discount_percent=Decimal("8"),
        discount_scope="eligible services",
    )

    # Preserve the original Phase 11.11 API ordering for regression compatibility.
    return (
        SimulatorBusiness(
            business_id=harvest.business_id,
            name=harvest.name,
            description=harvest.description,
            suggested_messages=(
                "What time do you close?",
                "Show me cooking oil",
                "1",
                "Order this",
                "2",
                "delivery",
                "Mufulira Central near the post office",
                "James +260970000001",
                "confirm",
                "Talk to a person",
            ),
            group="standard",
            adapter_type="tradeflow_standard",
            channel_instance_id="sim-wa-harvest",
            phone_e164=harvest.contact_phone,
        ),
        SimulatorBusiness(
            business_id=serahs.business_id,
            name=serahs.name,
            description=serahs.description,
            suggested_messages=(
                "I want to book an appointment",
                "1",
                tomorrow,
                "1",
                "anyone",
                "James +260970000001",
                "confirm",
            ),
            group="custom",
            adapter_type="tradeflow_serahs",
            channel_instance_id="sim-wa-serahs",
            phone_e164=serahs.contact_phone,
        ),
    )


def _seed_business_runtime(
    legacy_businesses: tuple[SimulatorBusiness, ...],
    now: datetime,
) -> tuple[
    tuple[BusinessProfile, ...],
    tuple[BusinessChannel, ...],
    tuple[SimulatorBusiness, ...],
    tuple[SimulatorConversation, ...],
]:
    del now
    standard_capabilities = frozenset(
        {
            Capability.BUSINESS_INFORMATION.value,
            Capability.BUSINESS_HOURS.value,
            Capability.FAQ.value,
            Capability.PRODUCT_CATALOGUE.value,
            Capability.PRODUCT_ORDER.value,
            Capability.COLLECTION.value,
            Capability.DELIVERY.value,
            Capability.HANDOVER.value,
        }
    )
    amac_capabilities = standard_capabilities.difference({Capability.DELIVERY.value})
    serah_capabilities = frozenset(
        {
            Capability.BUSINESS_INFORMATION.value,
            Capability.BUSINESS_HOURS.value,
            Capability.FAQ.value,
            Capability.CLIENT_IDENTIFY.value,
            Capability.CLIENT_CREATE.value,
            Capability.PRODUCT_CATALOGUE.value,
            Capability.PRODUCT_ORDER.value,
            Capability.COLLECTION.value,
            Capability.SERVICE_CATALOGUE.value,
            Capability.APPOINTMENT_CREATE.value,
            Capability.APPOINTMENT_RESCHEDULE.value,
            Capability.APPOINTMENT_CANCEL.value,
            Capability.LOYALTY_READ.value,
            Capability.HANDOVER.value,
        }
    )
    profiles = (
        BusinessProfile(
            business_id="harvest-big-shop",
            display_name="Harvest Big Shop",
            adapter_type="tradeflow_standard",
            declared_capabilities=standard_capabilities,
            business_type="retail",
        ),
        BusinessProfile(
            business_id="amac-enterprise",
            display_name="AMAC Enterprise",
            adapter_type="tradeflow_standard",
            declared_capabilities=amac_capabilities,
            business_type="retail",
        ),
        BusinessProfile(
            business_id="serahs-glow-lounge",
            display_name="Serah's Glow Lounge",
            adapter_type="tradeflow_serahs",
            declared_capabilities=serah_capabilities,
            business_type="beauty-salon-retail",
        ),
    )
    channels = (
        BusinessChannel(
            "sim-wa-harvest",
            "openwa-simulator",
            "harvest-big-shop",
            "+260970000001",
        ),
        BusinessChannel(
            "sim-wa-amac",
            "openwa-simulator",
            "amac-enterprise",
            "+260970000002",
        ),
        BusinessChannel(
            "sim-wa-serahs",
            "openwa-simulator",
            "serahs-glow-lounge",
            "+260976078440",
        ),
    )
    legacy_by_id = {item.business_id: item for item in legacy_businesses}
    workspace_businesses = (
        replace(
            legacy_by_id["harvest-big-shop"],
            capabilities=tuple(sorted(standard_capabilities)),
        ),
        SimulatorBusiness(
            business_id="amac-enterprise",
            name="AMAC Enterprise",
            description="Standard TradeFlow retail profile without delivery.",
            suggested_messages=(
                "Do you have Coca-Cola?",
                "Order one for collection",
                "Talk to a person",
            ),
            group="standard",
            adapter_type="tradeflow_standard",
            channel_instance_id="sim-wa-amac",
            phone_e164="+260970000002",
            capabilities=tuple(sorted(amac_capabilities)),
        ),
        replace(
            legacy_by_id["serahs-glow-lounge"],
            capabilities=tuple(sorted(serah_capabilities)),
        ),
    )
    conversations = (
        SimulatorConversation(
            "conv-harvest-mary",
            "harvest-big-shop",
            "sim-wa-harvest",
            "+260970000201",
            "Mary",
            "Cooking-oil discovery",
            "product_discovery",
            "new",
            ("Show me cooking oil", "1", "Order this", "2", "collection"),
            "Looking for cooking oil",
        ),
        SimulatorConversation(
            "conv-harvest-ruth",
            "harvest-big-shop",
            "sim-wa-harvest",
            "+260970000777",
            "Ruth",
            "Delivery order",
            "complete_order",
            "new",
            (
                "Order cooking oil",
                "1",
                "2",
                "delivery",
                "Mufulira Central near the post office",
                "Ruth +260970000777",
                "confirm",
            ),
            "Needs a delivery order",
        ),
        SimulatorConversation(
            "conv-amac-kelvin",
            "amac-enterprise",
            "sim-wa-amac",
            "+260970000301",
            "Kelvin",
            "Collection order",
            "standard_collection",
            "new",
            ("Do you have Coca-Cola?", "1", "Order this", "1", "collection"),
            "Asked about Coca-Cola",
        ),
        SimulatorConversation(
            "conv-amac-delivery-denied",
            "amac-enterprise",
            "sim-wa-amac",
            "+260970000302",
            "Angela",
            "Unsupported delivery",
            "capability_guard",
            "new",
            ("Order cooking oil for delivery",),
            "Tests a disabled capability",
        ),
        SimulatorConversation(
            "conv-serah-natasha",
            "serahs-glow-lounge",
            "sim-wa-serahs",
            "+260970000101",
            "Natasha",
            "Returning client and loyalty",
            "loyalty",
            "recognised",
            ("How many loyalty points do I have?", "I want to book an appointment"),
            "Returning Silver client",
        ),
        SimulatorConversation(
            "conv-serah-chanda",
            "serahs-glow-lounge",
            "sim-wa-serahs",
            "+260970000102",
            "Chanda",
            "New client booking",
            "client_and_booking",
            "new",
            (
                "I want to book knotless braids",
                "2",
                (datetime.now(UTC) + timedelta(days=2)).date().isoformat(),
                "1",
                "anyone",
                "Chanda +260970000102",
                "confirm",
            ),
            "Will create a minimal salon client",
        ),
        SimulatorConversation(
            "conv-serah-mercy",
            "serahs-glow-lounge",
            "sim-wa-serahs",
            "+260970000103",
            "Mercy",
            "Wig order",
            "product_order",
            "new",
            ("Show me black wigs", "1", "Order this", "1", "collection"),
            "Interested in a black wig",
        ),
        SimulatorConversation(
            "conv-serah-ruth",
            "serahs-glow-lounge",
            "sim-wa-serahs",
            "+260970000777",
            "Ruth",
            "Cross-business client",
            "cross_business",
            "recognised",
            ("How many loyalty points do I have?", "Book gel nails"),
            "Same person as Harvest, separate business state",
        ),
        SimulatorConversation(
            "conv-serah-handover",
            "serahs-glow-lounge",
            "sim-wa-serahs",
            "+260970000104",
            "Mercy",
            "Ask for Serah",
            "handover",
            "new",
            ("I want to speak to a person",),
            "Requests Serah personally",
        ),
    )
    return profiles, channels, workspace_businesses, conversations


__all__ = [
    "DeveloperConversationSimulator",
    "SimulatorBusiness",
    "SimulatorConversation",
    "SimulatorMessageResult",
    "SimulatorReply",
    "SimulatorSessionSnapshot",
]
