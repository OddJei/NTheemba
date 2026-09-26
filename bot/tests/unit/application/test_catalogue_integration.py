"""Application integration tests for two-turn product catalogue conversations."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from ntheemba.application.service import (
    NtheembaService,
    ProcessingStatus,
    ProcessMessageCommand,
)
from ntheemba.application.session_coordinator import SessionCoordinator
from ntheemba.application.workflow_router import WorkflowRouter
from ntheemba.domain.enums import ProductResolutionStatus, Stage
from ntheemba.ports.ncpc import CanonicalProduct
from ntheemba.ports.sessions import SessionKey
from ntheemba.ports.tradeflow import BusinessProduct
from ntheemba.services.interpretation import HybridInterpreter
from ntheemba.services.product_resolver import ProductResolver
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.catalogue import CatalogueWorkflow, build_catalogue_routes
from tests.fakes.audit import InMemoryAuditSink
from tests.fakes.ncpc import InMemoryNCPC
from tests.fakes.publisher import InMemoryOutgoingPublisher
from tests.fakes.sessions import (
    InMemoryDeduplicationStore,
    InMemorySessionLockManager,
    InMemorySessionRepository,
)
from tests.fakes.tradeflow import InMemoryTradeFlow


def _service() -> tuple[NtheembaService, InMemorySessionRepository, InMemoryOutgoingPublisher]:
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
            image_url="https://images.example.test/boom-500.jpg",
        ),
        "BP-1KG": BusinessProduct(
            business_product_id="BP-1KG",
            ncpc_product_id="NCPC-1KG",
            name="Boom Washing Powder 1kg",
            selling_price=Decimal("42"),
            currency="ZMW",
            available_quantity=4,
        ),
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
            CanonicalProduct(
                product_id="NCPC-1KG",
                canonical_name="Boom Washing Powder 1kg",
                brand="Boom",
                product_family="Washing Powder",
                size_value=Decimal("1"),
                size_unit="kg",
            ),
        )
    )
    workflow = CatalogueWorkflow(
        resolver=ProductResolver(ncpc=ncpc, tradeflow=tradeflow),
        tradeflow=tradeflow,
        responses=ResponseBuilder(),
    )
    publisher = InMemoryOutgoingPublisher()
    service = NtheembaService(
        coordinator=SessionCoordinator(
            repository=repository,
            locks=InMemorySessionLockManager(),
            clock=lambda: now,
        ),
        deduplication=InMemoryDeduplicationStore(clock=lambda: now),
        interpreter=HybridInterpreter(),
        router=WorkflowRouter(build_catalogue_routes(workflow)),
        publisher=publisher,
        audit=InMemoryAuditSink(),
        clock=lambda: now,
        request_id_factory=lambda: "REQ-1",
    )
    return service, repository, publisher


@pytest.mark.asyncio
async def test_search_then_number_selection_publishes_product_detail() -> None:
    service, repository, publisher = _service()

    first = await service.process_message(
        ProcessMessageCommand(
            business_id="BUS-1",
            customer_id="CUSTOMER-1",
            message_id="MSG-1",
            text="Do you have Boom product?",
            received_at=datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
        )
    )
    second = await service.process_message(
        ProcessMessageCommand(
            business_id="BUS-1",
            customer_id="CUSTOMER-1",
            message_id="MSG-2",
            text="1",
            received_at=datetime(2026, 7, 21, 10, 1, tzinfo=UTC),
        )
    )

    saved = await repository.load(SessionKey("BUS-1", "CUSTOMER-1"))
    assert first.status == ProcessingStatus.PROCESSED
    assert second.status == ProcessingStatus.PROCESSED
    assert saved is not None
    assert saved.stage == Stage.PRODUCT_SELECTED
    assert saved.product_resolution is not None
    assert saved.product_resolution.status == ProductResolutionStatus.RESOLVED
    assert len(publisher.messages) >= 3
    combined = "\n".join(
        value
        for message in publisher.messages
        for value in (message.text, message.caption)
        if value
    )
    assert "Which one would you like?" in combined
    assert "Price: K" in combined
    assert "BP-" not in combined
    assert "NCPC-" not in combined


@pytest.mark.asyncio
async def test_followup_number_selects_without_restarting_search() -> None:
    service, repository, _publisher = _service()

    await service.process_message(
        ProcessMessageCommand(
            business_id="BUS-1",
            customer_id="CUSTOMER-2",
            message_id="MSG-A",
            text="Do you have small Boom product?",
            received_at=datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
        )
    )
    result = await service.process_message(
        ProcessMessageCommand(
            business_id="BUS-1",
            customer_id="CUSTOMER-2",
            message_id="MSG-B",
            text="1",
            received_at=datetime(2026, 7, 21, 10, 1, tzinfo=UTC),
        )
    )

    saved = await repository.load(SessionKey("BUS-1", "CUSTOMER-2"))
    assert result.status == ProcessingStatus.PROCESSED
    assert saved is not None
    assert saved.stage == Stage.PRODUCT_SELECTED
    assert saved.product_resolution is not None
    assert saved.product_resolution.selected is not None
    assert saved.product_resolution.candidates == ()
