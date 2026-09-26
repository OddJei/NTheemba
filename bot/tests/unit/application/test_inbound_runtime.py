from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ntheemba.adapters.ncpc.in_memory import InMemoryNCPCAdapter
from ntheemba.adapters.secrets import StaticSecretResolver
from ntheemba.adapters.tradeflow.factory import HttpTradeFlowPortFactory
from ntheemba.application.gateway_worker import WorkerAction
from ntheemba.application.inbound_runtime import build_inbound_processing_runtime
from ntheemba.config import Settings
from ntheemba.domain.business import BusinessChannel, BusinessIntegration, BusinessProfile
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.gateway import InboundGatewayMessage
from ntheemba.domain.product_resolution import ProductQuery
from ntheemba.infrastructure.storage import build_storage_runtime
from ntheemba.ports.ncpc import CanonicalProduct


class _NoopNCPC(InMemoryNCPCAdapter):
    def __init__(self) -> None:
        super().__init__(products=())


class _UnavailableTradeFlowFactory:
    def build(self, integration: BusinessIntegration):
        raise AssertionError(f"TradeFlow should not be called for this message: {integration.integration_id}")


@pytest.mark.asyncio
async def test_inbound_worker_processes_queue_through_real_business_resolution() -> None:
    settings = Settings(environment="test", dev_tools_enabled=False)
    storage = build_storage_runtime(settings)
    await storage.open()
    try:
        business_id = "BUS-WORKER"
        await storage.business_registry.register_business(
            BusinessProfile(
                business_id,
                "Worker Business",
                "tradeflow",
                frozenset({Capability.BUSINESS_INFORMATION.value}),
            )
        )
        await storage.business_registry.register_channel(
            BusinessChannel("channel-worker", "whatsapp", business_id, "+260970000001")
        )
        runtime = build_inbound_processing_runtime(
            storage=storage,
            ncpc=_NoopNCPC(),
            tradeflow_factory=_UnavailableTradeFlowFactory(),
            audit=storage.audit_sink,
            consumer_id="worker-test",
            max_attempts=3,
        )
        delivery_id = await storage.gateway_queue.enqueue_inbound(
            InboundGatewayMessage(
                request_id="req-worker-1",
                message_id="msg-worker-1",
                channel_instance_id="channel-worker",
                provider="whatsapp",
                recipient_phone="+260970000001",
                customer_phone="+260970000002",
                text="hello",
                received_at=datetime(2026, 9, 4, 8, 0, tzinfo=UTC),
            )
        )
        result = await runtime.worker.run_once()
        assert result.action == WorkerAction.ACKNOWLEDGED
        assert result.delivery_id == delivery_id
    finally:
        await storage.close()


def test_standalone_worker_requires_durable_shared_backends() -> None:
    from ntheemba.inbound_worker import InboundWorkerConfigurationError, validate_inbound_worker_settings

    with pytest.raises(InboundWorkerConfigurationError, match="gateway_queue_backend"):
        validate_inbound_worker_settings(Settings(environment="test", dev_tools_enabled=False))


def test_standalone_worker_requires_ncpc_configuration_after_durable_backends() -> None:
    from ntheemba.inbound_worker import InboundWorkerConfigurationError, validate_inbound_worker_settings

    settings = Settings(
        environment="test",
        dev_tools_enabled=False,
        session_backend="redis",
        gateway_queue_backend="redis",
        customer_backend="postgres",
        business_backend="postgres",
        redis_url="redis://localhost:6379/0",
        postgres_dsn="postgresql://user:pass@localhost/db",
    )
    with pytest.raises(InboundWorkerConfigurationError, match="ncpc_base_url"):
        validate_inbound_worker_settings(settings)
