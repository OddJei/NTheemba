"""End-to-end application test for one complete order conversation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from ntheemba.application.service import NtheembaService, ProcessingStatus, ProcessMessageCommand
from ntheemba.application.session_coordinator import SessionCoordinator
from ntheemba.application.workflow_router import WorkflowRouter
from ntheemba.domain.enums import Stage
from ntheemba.ports.ncpc import CanonicalProduct
from ntheemba.ports.sessions import SessionKey
from ntheemba.ports.tradeflow import BusinessProduct
from ntheemba.services.interpretation import HybridInterpreter
from ntheemba.services.product_resolver import ProductResolver
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.catalogue import CatalogueWorkflow, build_catalogue_routes
from ntheemba.workflows.order import OrderWorkflow, build_order_routes
from tests.fakes.audit import InMemoryAuditSink
from tests.fakes.ncpc import InMemoryNCPC
from tests.fakes.publisher import InMemoryOutgoingPublisher
from tests.fakes.sessions import (
    InMemoryDeduplicationStore,
    InMemorySessionLockManager,
    InMemorySessionRepository,
)
from tests.fakes.tradeflow import InMemoryTradeFlow


def _service() -> tuple[
    NtheembaService,
    InMemorySessionRepository,
    InMemoryTradeFlow,
    InMemoryOutgoingPublisher,
]:
    now = datetime(2026, 7, 21, 10, 0, tzinfo=UTC)
    repository = InMemorySessionRepository()
    tradeflow = InMemoryTradeFlow()
    tradeflow.products["BUS-1"] = {
        "BP-500": BusinessProduct(
            business_product_id="BP-500",
            ncpc_product_id="NCPC-500",
            name="Boom Washing Powder 500g",
            selling_price=Decimal("24"),
            currency="ZMW",
            available_quantity=8,
            image_url="https://images.example.test/boom.jpg",
        )
    }
    ncpc = InMemoryNCPC(
        (
            CanonicalProduct(
                product_id="NCPC-500",
                canonical_name="Boom Washing Powder 500g",
                brand="Boom",
                product_family="Washing Powder",
                size_value=Decimal("500"),
                size_unit="g",
            ),
        )
    )
    responses = ResponseBuilder()
    catalogue = CatalogueWorkflow(
        resolver=ProductResolver(ncpc=ncpc, tradeflow=tradeflow),
        tradeflow=tradeflow,
        responses=responses,
    )
    order = OrderWorkflow(
        catalogue=catalogue,
        tradeflow=tradeflow,
        responses=responses,
    )
    routes = {
        **build_catalogue_routes(catalogue),
        **build_order_routes(order),
    }
    publisher = InMemoryOutgoingPublisher()
    service = NtheembaService(
        coordinator=SessionCoordinator(
            repository=repository,
            locks=InMemorySessionLockManager(),
            clock=lambda: now,
        ),
        deduplication=InMemoryDeduplicationStore(clock=lambda: now),
        interpreter=HybridInterpreter(),
        router=WorkflowRouter(routes),
        publisher=publisher,
        audit=InMemoryAuditSink(),
        clock=lambda: now,
        request_id_factory=lambda: "REQ-ORDER",
    )
    return service, repository, tradeflow, publisher


@pytest.mark.asyncio
async def test_complete_delivery_order_conversation() -> None:
    service, repository, tradeflow, publisher = _service()
    messages = (
        ("MSG-1", "order Boom 500g"),
        ("MSG-2", "yes"),
        ("MSG-3", "two"),
        ("MSG-4", "delivery"),
        ("MSG-5", "House 12 near the blue water tank"),
        ("MSG-6", "James Chisulo 0970000000"),
        ("MSG-7", "confirm"),
    )

    outcomes = []
    for index, (message_id, text) in enumerate(messages):
        outcomes.append(
            await service.process_message(
                ProcessMessageCommand(
                    business_id="BUS-1",
                    customer_id="CUSTOMER-1",
                    message_id=message_id,
                    text=text,
                    received_at=datetime(
                        2026,
                        7,
                        21,
                        10,
                        index,
                        tzinfo=UTC,
                    ),
                )
            )
        )

    saved = await repository.load(SessionKey("BUS-1", "CUSTOMER-1"))
    assert all(outcome.status == ProcessingStatus.PROCESSED for outcome in outcomes)
    assert saved is not None
    assert saved.stage == Stage.SUBMITTED
    assert saved.order_draft is not None
    assert saved.order_draft.quantity == 2
    assert saved.order_draft.delivery_details == "House 12 near the blue water tank"
    assert saved.order_draft.submitted
    assert len(tradeflow.orders) == 1
    assert (
        "check_product_availability",
        ("BUS-1", "BP-500", 2, ""),
    ) in tradeflow.calls
    combined = "\n".join(
        value
        for message in publisher.messages
        for value in (message.text, message.caption)
        if value
    )
    assert "Review your order request" in combined
    assert "Estimated total: K48.00" in combined
    assert "No payment has been taken" in combined
    assert "BP-500" not in combined
    assert "NCPC-500" not in combined
