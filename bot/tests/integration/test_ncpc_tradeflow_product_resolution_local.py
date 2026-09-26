"""Local NCPC -> TradeFlow -> Ntheemba product-resolution proof.

The fixture deliberately keeps NCPC identity shared while each TradeFlow
business owns its own price, stock state, public item id, and visibility.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ntheemba.application.workflow_router import WorkflowContext
from ntheemba.domain.enums import (
    Flow,
    IntentType,
    MessageRole,
    ProductResolutionOutcome,
    ProductResolutionStatus,
    Stage,
)
from ntheemba.domain.intents import EntitySet, Intent
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import TransitionPolicy
from ntheemba.ports.ncpc import CanonicalProduct
from ntheemba.ports.tradeflow import BusinessProduct
from ntheemba.services.product_resolver import ProductResolver
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.catalogue import CatalogueWorkflow
from tests.fakes.ncpc import InMemoryNCPC
from tests.fakes.tradeflow import InMemoryTradeFlow


def _ncpc() -> InMemoryNCPC:
    return InMemoryNCPC(
        (
            CanonicalProduct(
                product_id="PRD-COLA-500",
                variant_id="VAR-COLA-500",
                canonical_name="Coca-Cola 500 ml bottle",
                brand="Coca-Cola",
                product_family="Cola",
                variant="Bottle",
                size_value=Decimal("500"),
                size_unit="ml",
                barcode="5449000000996",
                aliases=("Coke", "Coca Cola"),
                catalogue_version="ncpc-local-v1",
            ),
            CanonicalProduct(
                product_id="PRD-COLA-2L",
                variant_id="VAR-COLA-2L",
                canonical_name="Coca-Cola 2 L bottle",
                brand="Coca-Cola",
                product_family="Cola",
                variant="Bottle",
                size_value=Decimal("2"),
                size_unit="l",
                barcode="5449000002222",
                aliases=("Coke", "Coca Cola"),
                catalogue_version="ncpc-local-v1",
            ),
            CanonicalProduct(
                product_id="PRD-MEALIE",
                variant_id="VAR-MEALIE-A",
                canonical_name="Business A Breakfast Mealie Meal 1 kg",
                brand="A Grain",
                product_family="Mealie Meal",
                size_value=Decimal("1"),
                size_unit="kg",
                aliases=("A mealie",),
                catalogue_version="ncpc-local-v1",
            ),
            CanonicalProduct(
                product_id="PRD-JUICE",
                variant_id="VAR-JUICE-B",
                canonical_name="Business B Mango Juice 1 L",
                brand="B Orchard",
                product_family="Juice",
                size_value=Decimal("1"),
                size_unit="l",
                aliases=("B juice",),
                catalogue_version="ncpc-local-v1",
            ),
        )
    )


def _tradeflow() -> InMemoryTradeFlow:
    tradeflow = InMemoryTradeFlow()
    tradeflow.products["BUS-A"] = {
        "A-COLA-500": BusinessProduct(
            business_product_id="A-COLA-500",
            ncpc_product_id="PRD-COLA-500",
            ncpc_variant_id="VAR-COLA-500",
            name="A Shop Coke 500 ml",
            selling_price=Decimal("12.50"),
            currency="ZMW",
            available_quantity=7,
        ),
        "A-COLA-2L": BusinessProduct(
            business_product_id="A-COLA-2L",
            ncpc_product_id="PRD-COLA-2L",
            ncpc_variant_id="VAR-COLA-2L",
            name="A Shop Coke 2 L",
            selling_price=Decimal("35.00"),
            currency="ZMW",
            available_quantity=2,
        ),
        "A-MEALIE": BusinessProduct(
            business_product_id="A-MEALIE",
            ncpc_product_id="PRD-MEALIE",
            ncpc_variant_id="VAR-MEALIE-A",
            name="A Shop Breakfast Mealie Meal",
            selling_price=Decimal("28.00"),
            currency="ZMW",
            available_quantity=4,
        ),
    }
    tradeflow.products["BUS-B"] = {
        "B-COLA-500": BusinessProduct(
            business_product_id="B-COLA-500",
            ncpc_product_id="PRD-COLA-500",
            ncpc_variant_id="VAR-COLA-500",
            name="B Market Coke 500 ml",
            selling_price=Decimal("14.75"),
            currency="ZMW",
            available_quantity=0,
        ),
        "B-JUICE": BusinessProduct(
            business_product_id="B-JUICE",
            ncpc_product_id="PRD-JUICE",
            ncpc_variant_id="VAR-JUICE-B",
            name="B Market Mango Juice",
            selling_price=Decimal("22.00"),
            currency="ZMW",
            available_quantity=6,
        ),
    }
    return tradeflow


def _workflow(
    tradeflow: InMemoryTradeFlow | None = None,
) -> tuple[CatalogueWorkflow, InMemoryNCPC, InMemoryTradeFlow]:
    ncpc = _ncpc()
    selected_tradeflow = tradeflow or _tradeflow()
    workflow = CatalogueWorkflow(
        resolver=ProductResolver(ncpc=ncpc, tradeflow=selected_tradeflow),
        tradeflow=selected_tradeflow,
        responses=ResponseBuilder(),
        transition_policy=TransitionPolicy(),
    )
    return workflow, ncpc, selected_tradeflow


def _session(business_id: str, customer_id: str = "CUSTOMER-1") -> Session:
    return Session.create(business_id, customer_id)


def _context(
    session: Session,
    intent_type: IntentType,
    *,
    query: str | None = None,
    selection: str | int | None = None,
    brand: str | None = None,
    product_family: str | None = None,
    barcode: str | None = None,
    extras: dict[str, str] | None = None,
    message_id: str = "MSG-1",
    request_id: str = "REQ-LOCAL",
) -> WorkflowContext:
    return WorkflowContext(
        session=session,
        intent=Intent(
            type=intent_type,
            role=(
                MessageRole.PENDING_ANSWER
                if intent_type == IntentType.SELECT_ITEM
                else MessageRole.NEW_REQUEST
            ),
            confidence=0.99,
            entities=EntitySet(
                query=query,
                selection=selection,
                brand=brand,
                product_family=product_family,
                barcode=barcode,
                raw_text=query or str(selection or barcode or ""),
                extras=extras or {},
            ),
        ),
        business_id=session.business_id,
        customer_id=session.customer_id,
        request_id=request_id,
        message_id=message_id,
    )


@pytest.mark.asyncio
async def test_exact_barcode_uses_selected_business_tradeflow_price_and_availability() -> None:
    workflow, _ncpc, tradeflow = _workflow()
    session = _session("BUS-A")

    first = await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            barcode="5449000000996",
            message_id="MSG-BARCODE",
        )
    )
    assert first.events[0].event_type == "catalogue.confirmation_requested"
    assert session.stage == Stage.ITEM_SELECTION
    assert session.product_resolution is not None
    assert session.product_resolution.selected is None
    assert len(session.product_resolution.candidates) == 1

    second = await workflow.handle(
        _context(session, IntentType.SELECT_ITEM, selection="yes", message_id="MSG-YES")
    )

    assert session.product_resolution is not None
    assert session.product_resolution.selected is not None
    assert session.stage == Stage.PRODUCT_SELECTED
    assert session.product_resolution.selected.business_id == "BUS-A"
    assert session.product_resolution.selected.ncpc_product_id == "PRD-COLA-500"
    assert session.product_resolution.selected.ncpc_variant_id == "VAR-COLA-500"
    assert session.product_resolution.selected.business_product_id == "A-COLA-500"
    assert session.product_resolution.selected.selling_price == Decimal("12.50")
    assert session.product_resolution.selected.available is True
    assert ("filter_business_products", ("BUS-A", ("VAR-COLA-500",))) in tradeflow.calls
    assert ("get_business_product", ("BUS-A", "A-COLA-500")) in tradeflow.calls
    assert second.events[0].event_type == "catalogue.product_selected"


@pytest.mark.asyncio
async def test_alias_typo_search_and_numbered_choice_do_not_cross_businesses() -> None:
    workflow, ncpc, tradeflow = _workflow()
    business_a = _session("BUS-A", "CUSTOMER-A")
    business_b = _session("BUS-B", "CUSTOMER-B")

    await workflow.handle(
        _context(
            business_a,
            IntentType.CATALOGUE_SEARCH,
            query="coc cola",
            brand="Coca-Cola",
            message_id="MSG-A-1",
        )
    )
    await workflow.handle(
        _context(
            business_b,
            IntentType.CATALOGUE_SEARCH,
            query="Coke",
            brand="Coca-Cola",
            message_id="MSG-B-1",
        )
    )
    await workflow.handle(
        _context(business_b, IntentType.SELECT_ITEM, selection=1, message_id="MSG-B-2")
    )

    assert business_a.product_resolution is not None
    assert business_a.product_resolution.status == ProductResolutionStatus.NEEDS_CLARIFICATION
    business_a_candidate_ids = {
        candidate.business_product_id for candidate in business_a.product_resolution.candidates
    }
    assert business_a_candidate_ids == {
        "A-COLA-500",
        "A-COLA-2L",
    }
    assert business_b.product_resolution is not None
    assert business_b.product_resolution.selected is not None
    assert business_b.product_resolution.selected.business_product_id == "B-COLA-500"
    assert business_b.product_resolution.selected.selling_price == Decimal("14.75")
    assert business_b.product_resolution.selected.available is False
    assert "A-COLA-500" not in repr(business_b.product_resolution)
    assert "A Shop" not in repr(business_b.product_resolution)
    assert ("filter_business_products", ("BUS-A", ("VAR-COLA-2L", "VAR-COLA-500"))) in (
        tradeflow.calls
    )
    assert ("filter_business_products", ("BUS-B", ("VAR-COLA-2L", "VAR-COLA-500"))) in (
        tradeflow.calls
    )
    assert len(ncpc.calls) == 2


@pytest.mark.asyncio
async def test_size_mismatch_keeps_customer_confirmation_and_shop_filtered_choices() -> None:
    workflow, ncpc, tradeflow = _workflow()
    session = _session("BUS-A", "CUSTOMER-SIZE")

    first = await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Coke 1 L",
            brand="Coca-Cola",
            extras={"size_value": "1", "size_unit": "l"},
            message_id="MSG-SIZE-1",
        )
    )

    assert first.events[0].event_type == "catalogue.clarification_requested"
    assert session.stage == Stage.PRODUCT_CLARIFICATION
    assert session.product_resolution is not None
    assert session.product_resolution.selected is None
    candidate_ids = tuple(
        candidate.business_product_id
        for candidate in session.product_resolution.candidates
    )
    assert set(candidate_ids) == {"A-COLA-500", "A-COLA-2L"}
    assert all(
        candidate.ncpc_variant_id in {"VAR-COLA-500", "VAR-COLA-2L"}
        for candidate in session.product_resolution.candidates
    )
    filter_calls = [
        call
        for call in tradeflow.calls
        if call[0] == "filter_business_products"
    ]
    assert len(filter_calls) == 1
    assert filter_calls[0][1][0] == "BUS-A"
    assert {"VAR-COLA-2L", "VAR-COLA-500"}.issubset(set(filter_calls[0][1][1]))

    ncpc_calls_before_selection = len(ncpc.calls)
    selected = await workflow.handle(
        _context(session, IntentType.SELECT_ITEM, selection="1", message_id="MSG-SIZE-2")
    )

    assert len(ncpc.calls) == ncpc_calls_before_selection
    assert selected.events[0].event_type == "catalogue.product_selected"
    assert selected.events[0].data["source"] == "customer_selection"
    assert session.product_resolution is not None
    assert session.product_resolution.selected is not None
    assert session.product_resolution.selected.business_id == "BUS-A"
    assert session.product_resolution.selected.business_product_id == candidate_ids[0]
    assert session.product_resolution.selected.ncpc_product_id.startswith("PRD-COLA")
    assert session.product_resolution.selected.ncpc_variant_id in {"VAR-COLA-500", "VAR-COLA-2L"}


@pytest.mark.asyncio
async def test_size_warning_is_translated_to_clarification_not_auto_selection() -> None:
    workflow, _ncpc, _tradeflow = _workflow()
    session = _session("BUS-A", "CUSTOMER-SIZE-WARNING")

    result = await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Coke 1 L",
            brand="Coca-Cola",
            extras={"size_value": "1", "size_unit": "l"},
            message_id="MSG-SIZE-WARNING",
        )
    )

    assert result.events[0].event_type == "catalogue.clarification_requested"
    assert result.replies[0].metadata["response_type"] == "product_clarification"
    assert session.stage == Stage.PRODUCT_CLARIFICATION
    assert session.product_resolution is not None
    assert session.product_resolution.selected is None
    assert {
        candidate.business_product_id for candidate in session.product_resolution.candidates
    } == {"A-COLA-500", "A-COLA-2L"}
    reply_text = result.replies[0].text or ""
    assert "A-COLA" not in reply_text
    assert "PRD-COLA" not in reply_text
    assert "VAR-COLA" not in reply_text


@pytest.mark.asyncio
async def test_ncpc_no_match_and_shop_no_match_are_distinct() -> None:
    workflow, _ncpc, _tradeflow = _workflow()
    ncpc_session = _session("BUS-A", "CUSTOMER-NCPC")
    shop_session = _session("BUS-A", "CUSTOMER-SHOP")

    ncpc_result = await workflow.handle(
        _context(ncpc_session, IntentType.CATALOGUE_SEARCH, query="unicorn cereal")
    )
    shop_result = await workflow.handle(
        _context(
            shop_session,
            IntentType.CATALOGUE_SEARCH,
            query="Business B Mango Juice",
            brand="B Orchard",
        )
    )

    assert ncpc_session.product_resolution is not None
    assert ncpc_session.product_resolution.outcome == ProductResolutionOutcome.NCPC_NO_MATCH
    assert ncpc_result.events[0].data["outcome"] == ProductResolutionOutcome.NCPC_NO_MATCH.value
    assert shop_session.product_resolution is not None
    assert shop_session.product_resolution.outcome == ProductResolutionOutcome.SHOP_NO_MATCH
    assert shop_result.events[0].data["outcome"] == ProductResolutionOutcome.SHOP_NO_MATCH.value


@pytest.mark.asyncio
async def test_multiple_shop_matches_numbered_choice_stale_choice_and_new_query_restart() -> None:
    workflow, ncpc, tradeflow = _workflow()
    session = _session("BUS-A")

    await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Coke",
            brand="Coca-Cola",
            message_id="MSG-1",
        )
    )
    assert session.product_resolution is not None
    assert session.stage == Stage.PRODUCT_CLARIFICATION
    assert len(session.product_resolution.candidates) == 2

    stale = session.product_resolution.scoped(
        business_id="BUS-A",
        customer_id="CUSTOMER-1",
        conversation_id=session.conversation_id,
        expires_at=session.started_at - timedelta(seconds=1),
        correlation_id="REQ-STALE",
    )
    session.product_resolution = stale
    stale_result = await workflow.handle(
        _context(session, IntentType.SELECT_ITEM, selection=2, message_id="MSG-STALE")
    )
    assert stale_result.events[0].event_type == "catalogue.selection_expired"
    assert session.product_resolution is None
    assert session.stage == Stage.CATALOGUE_SEARCH

    await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Coke",
            brand="Coca-Cola",
            message_id="MSG-RESTART-1",
        )
    )
    old_ncpc_calls = len(ncpc.calls)
    selected_result = await workflow.handle(
        _context(session, IntentType.SELECT_ITEM, selection=2, message_id="MSG-CHOICE")
    )

    assert len(ncpc.calls) == old_ncpc_calls
    assert session.stage == Stage.PRODUCT_SELECTED
    assert session.product_resolution is not None
    assert session.product_resolution.selected is not None
    assert session.product_resolution.selected.business_product_id == "A-COLA-2L"
    assert session.product_resolution.selected.selling_price == Decimal("35.00")
    assert selected_result.events[0].data["source"] == "customer_selection"
    assert ("get_business_product", ("BUS-A", "A-COLA-2L")) in tradeflow.calls

    restart_session = _session("BUS-A", "CUSTOMER-RESTART")
    await workflow.handle(
        _context(
            restart_session,
            IntentType.CATALOGUE_SEARCH,
            query="Coke",
            brand="Coca-Cola",
            message_id="MSG-OLD",
        )
    )
    restart_result = await workflow.handle(
        _context(
            restart_session,
            IntentType.CATALOGUE_SEARCH,
            query="A mealie",
            brand="A Grain",
            product_family="Mealie Meal",
            message_id="MSG-NEW",
        )
    )
    assert restart_result.events[0].event_type == "catalogue.confirmation_requested"
    assert restart_session.product_resolution is not None
    assert restart_session.product_resolution.query.original_text == "A mealie"
    assert tuple(
        candidate.business_product_id
        for candidate in restart_session.product_resolution.candidates
    ) == ("A-MEALIE",)


@pytest.mark.asyncio
async def test_cross_scope_pending_candidates_are_rejected_before_tradeflow_detail_read() -> None:
    workflow, _ncpc, tradeflow = _workflow()
    session = _session("BUS-A")
    await workflow.handle(
        _context(session, IntentType.CATALOGUE_SEARCH, query="Coke", brand="Coca-Cola")
    )
    assert session.product_resolution is not None
    before_calls = list(tradeflow.calls)
    session.product_resolution = session.product_resolution.scoped(
        business_id="BUS-B",
        customer_id="CUSTOMER-1",
        conversation_id=session.conversation_id,
        expires_at=session.started_at + timedelta(minutes=5),
        correlation_id="REQ-CROSS-SCOPE",
    )

    result = await workflow.handle(_context(session, IntentType.SELECT_ITEM, selection=1))

    assert result.events[0].event_type == "catalogue.selection_scope_rejected"
    assert session.product_resolution is None
    assert tradeflow.calls == before_calls
    assert session.flow == Flow.CATALOGUE
    assert session.stage == Stage.CATALOGUE_SEARCH
