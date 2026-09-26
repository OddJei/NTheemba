"""Gateway-level tenant context binding for pre-workflow client resolution."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ntheemba.adapters.customers import InMemoryCustomerDirectory
from ntheemba.application.customer_bridge import CustomerBridgeService
from ntheemba.application.gateway_service import GatewayMessageService
from ntheemba.application.runtime_context import current_runtime_context
from ntheemba.application.service import ProcessMessageOutcome, ProcessingStatus
from ntheemba.domain.business import BusinessChannel, BusinessIntegration, BusinessProfile, ResolvedBusinessContext
from ntheemba.domain.capabilities import Capability
from ntheemba.domain.gateway import InboundGatewayMessage
from ntheemba.observability.tracer import Tracer


class _BusinessResolver:
    def __init__(self, context: ResolvedBusinessContext) -> None:
        self.context = context

    async def resolve(self, _message: InboundGatewayMessage) -> ResolvedBusinessContext:
        return self.context


class _ContextCheckingClientPort:
    def __init__(self) -> None:
        self.seen_business_id = ""

    async def find_client_by_phone(self, business_id: str, _phone_e164: str):
        context = current_runtime_context()
        assert context is not None
        assert context.business.business_id == business_id
        self.seen_business_id = business_id
        return None

    async def create_minimal_client(self, *_args, **_kwargs):  # pragma: no cover - not used
        raise AssertionError("create_minimal_client should not be called")


@dataclass
class _CoreSpy:
    tracer: Tracer
    seen_business_id: str = ""

    async def process_message(self, command):
        self.seen_business_id = command.business_id
        return ProcessMessageOutcome(
            status=ProcessingStatus.PROCESSED,
            request_id=command.request_id,
        )


@pytest.mark.asyncio
async def test_gateway_binds_runtime_context_before_business_client_lookup() -> None:
    capabilities = frozenset({Capability.CLIENT_IDENTIFY})
    integration = BusinessIntegration(
        integration_id="serah-tradeflow",
        business_id="serah",
        adapter_type="tradeflow_serahs",
        base_url="https://tradeflow.local/serah",
        capabilities=frozenset({Capability.CLIENT_IDENTIFY.value}),
    )
    context = ResolvedBusinessContext(
        business=BusinessProfile(
            "serah",
            "Serah's Glow",
            "tradeflow_serahs",
            frozenset({Capability.CLIENT_IDENTIFY.value}),
        ),
        channel=BusinessChannel("wa-serah", "openwa", "serah", "+260970000002"),
        capabilities=capabilities,
        integrations=(integration,),
    )
    client_port = _ContextCheckingClientPort()
    core = _CoreSpy(tracer=Tracer())
    service = GatewayMessageService(
        businesses=_BusinessResolver(context),
        customers=CustomerBridgeService(
            customers=InMemoryCustomerDirectory(),
            clients=client_port,
        ),
        core=core,  # type: ignore[arg-type]
    )

    await service.process(
        InboundGatewayMessage(
            request_id="REQ-1",
            message_id="MSG-1",
            channel_instance_id="wa-serah",
            provider="openwa",
            recipient_phone="+260970000002",
            customer_phone="+260977000001",
            text="Hi",
        )
    )

    assert client_port.seen_business_id == "serah"
    assert core.seen_business_id == "serah"
    assert current_runtime_context() is None
