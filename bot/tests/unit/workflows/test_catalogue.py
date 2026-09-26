"""Tests for the product catalogue workflow."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ntheemba.application.workflow_router import WorkflowContext
from ntheemba.domain.enums import (
    ConversationMode,
    Flow,
    IntentType,
    MessageRole,
    ProductResolutionOutcome,
    ProductResolutionStatus,
    SessionStatus,
    Stage,
)
from ntheemba.domain.intents import EntitySet, Intent
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import TransitionPolicy
from ntheemba.ports.ncpc import CanonicalProduct
from ntheemba.ports.tradeflow import BusinessProduct
from ntheemba.services.product_resolver import ProductResolver
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.catalogue import (
    CatalogueStateError,
    CatalogueWorkflow,
    CatalogueWorkflowConfig,
    UnsupportedCatalogueIntentError,
    build_catalogue_routes,
)
from tests.fakes.ncpc import InMemoryNCPC
from tests.fakes.tradeflow import InMemoryTradeFlow


def _catalogue() -> tuple[InMemoryNCPC, InMemoryTradeFlow]:
    ncpc = InMemoryNCPC(
        (
            CanonicalProduct(
                product_id="NCPC-250",
                variant_id="VAR-250",
                canonical_name="Boom Washing Powder 250g",
                brand="Boom",
                product_family="Washing Powder",
                size_value=Decimal("250"),
                size_unit="g",
                catalogue_version="cat-v1",
            ),
            CanonicalProduct(
                product_id="NCPC-500",
                variant_id="VAR-500",
                canonical_name="Boom Washing Powder 500g",
                brand="Boom",
                product_family="Washing Powder",
                size_value=Decimal("500"),
                size_unit="g",
                catalogue_version="cat-v1",
            ),
            CanonicalProduct(
                product_id="NCPC-1KG",
                variant_id="VAR-1KG",
                canonical_name="Boom Washing Powder 1kg",
                brand="Boom",
                product_family="Washing Powder",
                size_value=Decimal("1"),
                size_unit="kg",
                catalogue_version="cat-v1",
            ),
        )
    )
    tradeflow = InMemoryTradeFlow()
    tradeflow.products["BUS-1"] = {
        "BP-250": BusinessProduct(
            business_product_id="BP-250",
            ncpc_product_id="NCPC-250",
            ncpc_variant_id="VAR-250",
            name="Boom Washing Powder 250g",
            selling_price=Decimal("15"),
            currency="ZMW",
            available_quantity=0,
        ),
        "BP-500": BusinessProduct(
            business_product_id="BP-500",
            ncpc_product_id="NCPC-500",
            ncpc_variant_id="VAR-500",
            name="Boom Washing Powder 500g",
            selling_price=Decimal("24"),
            currency="ZMW",
            available_quantity=8,
            image_url="https://images.example.test/boom-500.jpg",
        ),
        "BP-1KG": BusinessProduct(
            business_product_id="BP-1KG",
            ncpc_product_id="NCPC-1KG",
            ncpc_variant_id="VAR-1KG",
            name="Boom Washing Powder 1kg",
            selling_price=Decimal("42"),
            currency="ZMW",
            available_quantity=4,
        ),
    }
    return ncpc, tradeflow


def _workflow(
    *,
    tradeflow: InMemoryTradeFlow | None = None,
    maximum_selection_attempts: int = 3,
) -> CatalogueWorkflow:
    ncpc, seeded_tradeflow = _catalogue()
    selected_tradeflow = tradeflow or seeded_tradeflow
    return CatalogueWorkflow(
        resolver=ProductResolver(ncpc=ncpc, tradeflow=selected_tradeflow),
        tradeflow=selected_tradeflow,
        responses=ResponseBuilder(),
        transition_policy=TransitionPolicy(),
        config=CatalogueWorkflowConfig(maximum_selection_attempts=maximum_selection_attempts),
    )


class FailingTradeFlow(InMemoryTradeFlow):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    async def filter_business_products(
        self,
        business_id: str,
        ncpc_variant_ids: tuple[str, ...],
    ) -> tuple[BusinessProduct, ...]:
        raise self.error

    async def get_business_product(
        self,
        business_id: str,
        business_product_id: str,
    ) -> BusinessProduct | None:
        raise self.error


def _context(
    session: Session,
    intent_type: IntentType,
    *,
    query: str | None = None,
    selection: str | int | None = None,
    brand: str | None = None,
) -> WorkflowContext:
    raw = query or (str(selection) if selection is not None else "")
    return WorkflowContext(
        session=session,
        intent=Intent(
            type=intent_type,
            role=(
                MessageRole.NEW_REQUEST
                if intent_type == IntentType.CATALOGUE_SEARCH
                else MessageRole.PENDING_ANSWER
            ),
            confidence=0.99,
            entities=EntitySet(
                query=query,
                selection=selection,
                brand=brand,
                raw_text=raw,
            ),
        ),
        business_id=session.business_id,
        customer_id=session.customer_id,
        request_id="REQ-1",
        message_id="MSG-1",
    )


@pytest.mark.asyncio
async def test_broad_search_saves_candidates_and_asks_for_selection() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")

    result = await _workflow().handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Boom",
            brand="Boom",
        )
    )

    assert session.flow == Flow.CATALOGUE
    assert session.stage == Stage.PRODUCT_CLARIFICATION
    assert session.product_resolution is not None
    assert session.product_resolution.status == ProductResolutionStatus.NEEDS_CLARIFICATION
    assert session.pending_question is not None
    assert session.pending_question.expected_intents == frozenset({IntentType.SELECT_ITEM})
    assert len(session.pending_question.metadata["options"]) == 3
    assert result.replies[0].metadata["response_type"] == "product_clarification"
    assert result.events[0].event_type == "catalogue.clarification_requested"


@pytest.mark.asyncio
async def test_exact_search_still_asks_for_customer_confirmation() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")

    result = await _workflow().handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Boom Washing Powder 500g",
            brand="Boom",
        )
    )

    assert session.stage == Stage.PRODUCT_CLARIFICATION
    assert session.product_resolution is not None
    assert session.product_resolution.selected is None
    assert session.product_resolution.business_id == "BUS-1"
    assert session.product_resolution.customer_id == "CUSTOMER-1"
    assert session.product_resolution.conversation_id == session.conversation_id
    assert session.product_resolution.correlation_id == "REQ-1"
    assert session.product_resolution.catalogue_version == "cat-v1"
    assert session.product_resolution.expires_at is not None
    assert [candidate.candidate_order for candidate in session.product_resolution.candidates] == [
        1,
        2,
        3,
    ]
    assert result.replies[0].metadata["response_type"] == "product_clarification"
    combined = result.replies[0].text or ""
    assert "BP-500" not in combined
    assert "NCPC-500" not in combined
    assert "VAR-500" not in combined
    assert "ZMW 24.00" in combined


@pytest.mark.asyncio
async def test_numbered_selection_resolves_saved_candidate() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    ncpc, tradeflow = _catalogue()
    workflow = CatalogueWorkflow(
        resolver=ProductResolver(ncpc=ncpc, tradeflow=tradeflow),
        tradeflow=tradeflow,
        responses=ResponseBuilder(),
        transition_policy=TransitionPolicy(),
    )
    await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Boom",
            brand="Boom",
        )
    )

    assert ("filter_business_products", ("BUS-1", ("VAR-1KG", "VAR-250", "VAR-500"))) in (
        tradeflow.calls
    )
    ncpc_call_count = len(ncpc.calls)
    expected_name = session.product_resolution.candidates[1].name  # type: ignore[union-attr]
    result = await workflow.handle(_context(session, IntentType.SELECT_ITEM, selection=2))

    assert len(ncpc.calls) == ncpc_call_count
    assert session.stage == Stage.PRODUCT_SELECTED
    assert session.pending_question is None
    assert session.clarification_count == 0
    assert session.product_resolution is not None
    assert session.product_resolution.selected is not None
    assert session.product_resolution.selected.name == expected_name
    assert session.product_resolution.candidates == ()
    assert session.product_resolution.selected.business_id == "BUS-1"
    assert session.product_resolution.selected.business_product_id == "BP-500"
    assert session.product_resolution.selected.ncpc_product_id == "NCPC-500"
    assert session.product_resolution.selected.ncpc_variant_id == "VAR-500"
    assert result.events[0].data["source"] == "customer_selection"


@pytest.mark.asyncio
async def test_size_selection_resolves_unique_candidate() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    workflow = _workflow()
    await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Boom",
            brand="Boom",
        )
    )

    await workflow.handle(_context(session, IntentType.SELECT_ITEM, selection="500g"))

    assert session.product_resolution is not None
    assert session.product_resolution.selected is not None
    assert session.product_resolution.selected.business_product_id == "BP-500"


@pytest.mark.asyncio
async def test_invalid_selection_repeats_options_and_counts_attempt() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    workflow = _workflow()
    await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Boom",
            brand="Boom",
        )
    )

    result = await workflow.handle(
        _context(session, IntentType.SELECT_ITEM, selection="blue packet")
    )

    assert session.stage == Stage.PRODUCT_CLARIFICATION
    assert session.clarification_count == 1
    assert result.replies[0].metadata["response_type"] == "product_clarification"
    assert result.events[0].event_type == "catalogue.selection_invalid"


@pytest.mark.asyncio
async def test_repeated_invalid_selection_escalates_to_handover() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    workflow = _workflow(maximum_selection_attempts=2)
    await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Boom",
            brand="Boom",
        )
    )

    await workflow.handle(_context(session, IntentType.SELECT_ITEM, selection="wrong one"))
    await workflow.handle(_context(session, IntentType.SELECT_ITEM, selection="still wrong"))
    result = await workflow.handle(
        _context(session, IntentType.SELECT_ITEM, selection="again wrong")
    )

    assert session.flow == Flow.HANDOVER
    assert session.stage == Stage.WAITING_FOR_HUMAN
    assert session.mode == ConversationMode.HUMAN
    assert session.status == SessionStatus.PAUSED
    assert session.suspended_state is not None
    assert result.replies[0].metadata["response_type"] == "handover_requested"
    assert result.events[0].event_type == "catalogue.selection_escalated"


@pytest.mark.asyncio
async def test_new_search_replaces_previous_clarification_state() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    workflow = _workflow()
    await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Boom",
            brand="Boom",
        )
    )

    result = await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Boom Washing Powder 500g",
            brand="Boom",
        )
    )

    assert session.stage == Stage.PRODUCT_CLARIFICATION
    assert session.pending_question is not None
    assert session.product_resolution is not None
    assert session.product_resolution.selected is None
    assert session.product_resolution.query.original_text == "Boom Washing Powder 500g"
    assert result.events[0].event_type == "catalogue.clarification_requested"


@pytest.mark.asyncio
async def test_expired_pending_set_blocks_stale_selection() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    workflow = _workflow()
    await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Boom",
            brand="Boom",
        )
    )
    assert session.product_resolution is not None
    session.product_resolution = session.product_resolution.scoped(
        business_id="BUS-1",
        customer_id="CUSTOMER-1",
        conversation_id=session.conversation_id,
        expires_at=session.started_at - timedelta(seconds=1),
        correlation_id="REQ-old",
    )

    result = await workflow.handle(_context(session, IntentType.SELECT_ITEM, selection=2))

    assert session.stage == Stage.CATALOGUE_SEARCH
    assert session.product_resolution is None
    assert result.events[0].event_type == "catalogue.selection_expired"


@pytest.mark.asyncio
async def test_shop_cannot_use_another_shop_pending_candidates() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    workflow = _workflow()
    await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Boom",
            brand="Boom",
        )
    )
    assert session.product_resolution is not None
    session.product_resolution = session.product_resolution.scoped(
        business_id="BUS-2",
        customer_id="CUSTOMER-1",
        conversation_id=session.conversation_id,
        expires_at=session.started_at + timedelta(minutes=10),
        correlation_id="REQ-other",
    )

    result = await workflow.handle(_context(session, IntentType.SELECT_ITEM, selection=2))

    assert session.stage == Stage.CATALOGUE_SEARCH
    assert session.product_resolution is None
    assert result.events[0].event_type == "catalogue.selection_scope_rejected"


@pytest.mark.asyncio
async def test_none_of_these_requests_human_handover() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    workflow = _workflow()
    await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Boom",
            brand="Boom",
        )
    )

    result = await workflow.handle(
        _context(session, IntentType.SELECT_ITEM, selection="none of these")
    )

    assert session.flow == Flow.HANDOVER
    assert session.stage == Stage.WAITING_FOR_HUMAN
    assert result.events[0].event_type == "catalogue.none_of_these_handover"


@pytest.mark.asyncio
async def test_product_removed_before_selection_returns_to_search() -> None:
    ncpc, tradeflow = _catalogue()
    workflow = CatalogueWorkflow(
        resolver=ProductResolver(ncpc=ncpc, tradeflow=tradeflow),
        tradeflow=tradeflow,
        responses=ResponseBuilder(),
        transition_policy=TransitionPolicy(),
    )
    session = Session.create("BUS-1", "CUSTOMER-1")
    await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Boom",
            brand="Boom",
        )
    )
    chosen = session.product_resolution.candidates[0]  # type: ignore[union-attr]
    assert chosen.business_product_id is not None
    tradeflow.products["BUS-1"].pop(chosen.business_product_id)

    result = await workflow.handle(_context(session, IntentType.SELECT_ITEM, selection=1))

    assert session.stage == Stage.CATALOGUE_SEARCH
    assert session.product_resolution is not None
    assert session.product_resolution.status == ProductResolutionStatus.NO_MATCH
    assert result.events[0].event_type == "catalogue.product_no_longer_public"


@pytest.mark.asyncio
async def test_no_match_stays_ready_for_another_search() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")

    result = await _workflow().handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Unicorn cereal",
        )
    )

    assert session.flow == Flow.CATALOGUE
    assert session.stage == Stage.CATALOGUE_SEARCH
    assert session.product_resolution is not None
    assert session.product_resolution.status == ProductResolutionStatus.NO_MATCH
    assert session.product_resolution.outcome == ProductResolutionOutcome.NCPC_NO_MATCH
    assert result.replies[0].metadata["response_type"] == "product_resolution_failure"
    assert result.replies[0].metadata["outcome"] == ProductResolutionOutcome.NCPC_NO_MATCH.value


@pytest.mark.asyncio
async def test_tradeflow_timeout_does_not_save_or_leak_candidates() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    ncpc, _tradeflow = _catalogue()
    failing_tradeflow = FailingTradeFlow(TimeoutError("private sheet id and token"))
    workflow = CatalogueWorkflow(
        resolver=ProductResolver(ncpc=ncpc, tradeflow=failing_tradeflow),
        tradeflow=failing_tradeflow,
        responses=ResponseBuilder(),
        transition_policy=TransitionPolicy(),
    )

    result = await workflow.handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Boom",
            brand="Boom",
        )
    )

    assert session.product_resolution is None
    assert session.stage == Stage.CATALOGUE_SEARCH
    assert result.replies[0].metadata["outcome"] == ProductResolutionOutcome.TRADEFLOW_TIMEOUT.value
    assert result.events[0].event_type == "catalogue.dependency_failed"
    assert result.events[0].data["correlation_id"] == "REQ-1"
    assert result.events[0].data["outcome"] == ProductResolutionOutcome.TRADEFLOW_TIMEOUT.value
    assert result.events[0].data["dependency"] == "tradeflow"
    assert result.events[0].data["retryable"] is True
    assert isinstance(result.events[0].data["elapsed_ms"], int)
    event_text = repr(dict(result.events[0].data))
    reply_text = result.replies[0].text or ""
    assert "private sheet" not in event_text
    assert "token" not in event_text.lower()
    assert "Boom Washing Powder" not in reply_text
    assert "ZMW" not in reply_text
    assert "BP-" not in reply_text


@pytest.mark.asyncio
async def test_auth_and_malformed_failures_have_non_retryable_outcomes() -> None:
    for error, outcome in (
        (PermissionError("credential failed"), ProductResolutionOutcome.AUTH_FAILURE),
        (ValueError("full raw payload"), ProductResolutionOutcome.MALFORMED_RESPONSE),
    ):
        session = Session.create("BUS-1", "CUSTOMER-1")
        ncpc, _tradeflow = _catalogue()
        failing_tradeflow = FailingTradeFlow(error)
        workflow = CatalogueWorkflow(
            resolver=ProductResolver(ncpc=ncpc, tradeflow=failing_tradeflow),
            tradeflow=failing_tradeflow,
            responses=ResponseBuilder(),
            transition_policy=TransitionPolicy(),
        )

        result = await workflow.handle(
            _context(session, IntentType.CATALOGUE_SEARCH, query="Boom", brand="Boom")
        )

        assert session.product_resolution is None
        assert result.replies[0].metadata["outcome"] == outcome.value
        assert result.events[0].data["outcome"] == outcome.value
        assert result.events[0].data["retryable"] is False
        assert "credential" not in repr(dict(result.events[0].data)).lower()


@pytest.mark.asyncio
async def test_live_product_timeout_does_not_select_item_or_initialize_order_draft() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    ncpc, tradeflow = _catalogue()
    workflow = CatalogueWorkflow(
        resolver=ProductResolver(ncpc=ncpc, tradeflow=tradeflow),
        tradeflow=tradeflow,
        responses=ResponseBuilder(),
        transition_policy=TransitionPolicy(),
    )
    await workflow.handle(
        _context(session, IntentType.CATALOGUE_SEARCH, query="Boom", brand="Boom")
    )
    assert session.product_resolution is not None
    failing_tradeflow = FailingTradeFlow(TimeoutError("product list"))
    workflow.tradeflow = failing_tradeflow

    result = await workflow.handle(_context(session, IntentType.SELECT_ITEM, selection=2))

    assert session.stage == Stage.PRODUCT_CLARIFICATION
    assert session.product_resolution is not None
    assert session.product_resolution.selected is None
    assert session.order_draft is None
    assert result.replies[0].metadata["outcome"] == ProductResolutionOutcome.TRADEFLOW_TIMEOUT.value
    assert "Boom Washing Powder" not in (result.replies[0].text or "")


@pytest.mark.asyncio
async def test_expired_session_has_deterministic_customer_response() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.status = SessionStatus.EXPIRED

    result = await _workflow().handle(
        _context(session, IntentType.CATALOGUE_SEARCH, query="Boom", brand="Boom")
    )

    assert result.replies[0].metadata["outcome"] == ProductResolutionOutcome.SESSION_EXPIRED.value
    assert result.events[0].event_type == "catalogue.session_expired"
    assert result.events[0].data["outcome"] == ProductResolutionOutcome.SESSION_EXPIRED.value


@pytest.mark.asyncio
async def test_order_owned_search_keeps_order_flow() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    policy = TransitionPolicy()
    session.transition_to(policy, Flow.ORDER, Stage.CATALOGUE_SEARCH)

    await _workflow().handle(
        _context(
            session,
            IntentType.CATALOGUE_SEARCH,
            query="Boom",
            brand="Boom",
        )
    )

    assert session.flow == Flow.ORDER
    assert session.stage == Stage.PRODUCT_CLARIFICATION


@pytest.mark.asyncio
async def test_missing_saved_resolution_rejects_selection() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")
    policy = TransitionPolicy()
    session.transition_to(policy, Flow.CATALOGUE, Stage.CATALOGUE_SEARCH)

    with pytest.raises(CatalogueStateError, match="saved selectable"):
        await _workflow().handle(_context(session, IntentType.SELECT_ITEM, selection=1))


@pytest.mark.asyncio
async def test_unsupported_intent_is_rejected() -> None:
    session = Session.create("BUS-1", "CUSTOMER-1")

    with pytest.raises(UnsupportedCatalogueIntentError):
        await _workflow().handle(_context(session, IntentType.START_ORDER))


def test_route_helper_registers_search_and_selection() -> None:
    workflow = _workflow()

    routes = build_catalogue_routes(workflow)

    assert set(routes) == {
        IntentType.CATALOGUE_SEARCH,
        IntentType.SELECT_ITEM,
    }
    assert all(handler is workflow for handler in routes.values())
