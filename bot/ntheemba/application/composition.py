"""Production-shaped deterministic Ntheemba runtime composition.

This module deliberately stops at the deterministic boundary: the interpreter is rule-first
and has no model provider by default, tenant configuration comes from the configured business
registry, NCPC is a shared identity reader, and TradeFlow is selected dynamically from the
resolved tenant integration.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from ntheemba.adapters.tradeflow import DynamicTradeFlowPort
from ntheemba.adapters.tradeflow.factory import TradeFlowPortFactory
from ntheemba.application.capability_runtime import CapabilityAwareWorkflowRouter
from ntheemba.application.customer_workflow import CustomerAwareWorkflowHandler
from ntheemba.application.flow_dispatcher import FlowAwareWorkflowHandler
from ntheemba.application.gateway_service import GatewayMessageService
from ntheemba.application.service import Interpreter, NtheembaService, ReplyLocalizer
from ntheemba.application.workflow_router import WorkflowHandler, WorkflowRouter
from ntheemba.domain.enums import IntentType
from ntheemba.infrastructure.storage import StorageRuntime
from ntheemba.observability.tracer import Tracer
from ntheemba.ports.audit import AuditSink
from ntheemba.ports.ncpc import NCPCPort
from ntheemba.ports.publisher import OutgoingPublisher
from ntheemba.services.interpretation import HybridInterpreter
from ntheemba.services.product_resolver import ProductResolver
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.booking import BookingWorkflow
from ntheemba.workflows.catalogue import CatalogueWorkflow
from ntheemba.workflows.handover import HandoverWorkflow
from ntheemba.workflows.information import InformationWorkflow
from ntheemba.workflows.loyalty import LoyaltyWorkflow
from ntheemba.workflows.order import OrderWorkflow


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class DeterministicRuntime:
    """Reusable service graph for one Ntheemba process."""

    gateway: GatewayMessageService
    core: NtheembaService
    tradeflow: DynamicTradeFlowPort
    product_resolver: ProductResolver
    router: CapabilityAwareWorkflowRouter


def build_deterministic_runtime(
    *,
    storage: StorageRuntime,
    ncpc: NCPCPort,
    tradeflow_factory: TradeFlowPortFactory,
    audit: AuditSink,
    interpreter: Interpreter | None = None,
    reply_localizer: ReplyLocalizer | None = None,
    publisher: OutgoingPublisher | None = None,
    tracer: Tracer | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> DeterministicRuntime:
    """Compose deterministic Ntheemba over configured durable/runtime ports.

    No LLM is enabled unless the caller explicitly supplies a different interpreter.
    The default ``HybridInterpreter`` therefore runs deterministic rules only.
    """

    runtime_tracer = tracer or Tracer()
    responses = ResponseBuilder()
    tradeflow = DynamicTradeFlowPort(factory=tradeflow_factory)
    resolver = ProductResolver(ncpc=ncpc, tradeflow=tradeflow)

    catalogue = CatalogueWorkflow(
        resolver=resolver,
        tradeflow=tradeflow,
        responses=responses,
    )
    order = OrderWorkflow(
        catalogue=catalogue,
        tradeflow=tradeflow,
        responses=responses,
    )
    booking = BookingWorkflow(
        tradeflow=tradeflow,
        responses=responses,
        clock=clock,
    )
    information = InformationWorkflow(
        tradeflow=tradeflow,
        responses=responses,
        clock=clock,
    )
    customers = storage.build_customer_bridge(tradeflow)
    loyalty = LoyaltyWorkflow(customers=customers, tradeflow=tradeflow)
    handover = HandoverWorkflow(responses=responses)

    flow_dispatcher: WorkflowHandler = FlowAwareWorkflowHandler(
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
        customers=customers,
    )
    routes = {intent_type: dispatcher for intent_type in IntentType}
    base_router = WorkflowRouter(routes, tracer=runtime_tracer)
    router = CapabilityAwareWorkflowRouter(base_router, tracer=runtime_tracer)

    core = NtheembaService(
        coordinator=storage.build_session_coordinator(),
        deduplication=storage.deduplication,
        interpreter=interpreter or HybridInterpreter(),
        router=router,
        publisher=publisher or storage.build_gateway_publisher(),
        audit=audit,
        clock=clock,
        tracer=runtime_tracer,
        reply_localizer=reply_localizer,
    )
    gateway = GatewayMessageService(
        businesses=storage.build_business_context_resolver(tracer=runtime_tracer),
        customers=customers,
        core=core,
        tracer=runtime_tracer,
    )
    return DeterministicRuntime(
        gateway=gateway,
        core=core,
        tradeflow=tradeflow,
        product_resolver=resolver,
        router=router,
    )
