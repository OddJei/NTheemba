"""Reusable inbound processing composition for the real gateway queue."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from ntheemba.adapters.tradeflow.factory import TradeFlowPortFactory
from ntheemba.application.composition import DeterministicRuntime, build_deterministic_runtime
from ntheemba.application.gateway_worker import InboundGatewayWorker
from ntheemba.application.inbound_idempotency import InboundMessageIdempotency
from ntheemba.application.marketplace import (
    MarketplaceHandoffConsumptionService,
    MarketplaceHandoffService,
    MarketplaceOrderBridgeService,
    MarketplaceProductDiscoveryService,
)
from ntheemba.application.platform_workflow_runtime import PlatformWorkflowRouter
from ntheemba.application.service import ReplyLocalizer
from ntheemba.application.unified_gateway_service import UnifiedGatewayMessageService
from ntheemba.infrastructure.storage import StorageRuntime
from ntheemba.ports.audit import AuditSink
from ntheemba.ports.ncpc import NCPCPort
from ntheemba.services.interpretation import ModelIntentProvider


@dataclass(frozen=True, slots=True)
class InboundProcessingRuntime:
    """Deterministic business/platform runtime plus its reliable inbound worker."""

    deterministic: DeterministicRuntime
    service: UnifiedGatewayMessageService
    worker: InboundGatewayWorker


def build_inbound_processing_runtime(
    *,
    storage: StorageRuntime,
    ncpc: NCPCPort,
    tradeflow_factory: TradeFlowPortFactory,
    audit: AuditSink,
    consumer_id: str,
    max_attempts: int,
    model: ModelIntentProvider | None = None,
    reply_localizer: ReplyLocalizer | None = None,
) -> InboundProcessingRuntime:
    """Build one inbound worker over the same deterministic graph used by E2E tests.

    The optional model is interpretation-only. Business/channel resolution, capability
    guards, NCPC/TradeFlow selection and workflow state remain deterministic.
    """

    deterministic = build_deterministic_runtime(
        storage=storage,
        ncpc=ncpc,
        tradeflow_factory=tradeflow_factory,
        audit=audit,
        interpreter=None if model is None else _hybrid_interpreter(model),
        reply_localizer=reply_localizer,
    )
    customers = storage.build_customer_bridge(deterministic.tradeflow)
    discovery = MarketplaceProductDiscoveryService(
        businesses=storage.business_registry,
        marketplace=storage.marketplace_registry,
        ncpc=ncpc,
        tradeflow_factory=tradeflow_factory,
    )
    handoff = MarketplaceHandoffService(
        businesses=storage.business_registry,
        marketplace=storage.marketplace_registry,
        tradeflow_factory=tradeflow_factory,
        audit=audit,
    )
    consumption = MarketplaceHandoffConsumptionService(
        businesses=storage.business_registry,
        marketplace=storage.marketplace_registry,
        tradeflow_factory=tradeflow_factory,
        audit=audit,
    )
    platform_router = PlatformWorkflowRouter(
        discovery=discovery,
        handoff=handoff,
        consumption=consumption,
    )
    order_bridge = MarketplaceOrderBridgeService(
        runtime=deterministic.core.workflow_runtime,
    )
    unified = UnifiedGatewayMessageService(
        contexts=storage.build_channel_context_resolver(tracer=deterministic.core.tracer),
        business_service=deterministic.gateway,
        customers=customers,
        core=deterministic.core,
        platform_sessions=storage.build_platform_session_coordinator(),
        platform_router=platform_router,
        handoff_consumption=consumption,
        order_bridge=order_bridge,
        audit=audit,
    )
    return InboundProcessingRuntime(
        deterministic=deterministic,
        service=unified,
        worker=InboundGatewayWorker(
            queue=storage.gateway_queue,
            service=unified,
            consumer_id=consumer_id,
            max_attempts=max_attempts,
            inbound_idempotency=InboundMessageIdempotency(
                storage.idempotency,
                ttl=timedelta(seconds=storage.settings.deduplication_ttl_seconds),
            ),
            audit=audit,
            tracer=deterministic.core.tracer,
        ),
    )


def _hybrid_interpreter(model: ModelIntentProvider):
    # Local import keeps the worker composition dependent on the interpretation
    # interface rather than a concrete remote-model transport.
    from ntheemba.services.interpretation import HybridInterpreter

    return HybridInterpreter(model=model)
