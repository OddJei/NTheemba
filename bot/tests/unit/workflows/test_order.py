"""Tests for the order collection and submission workflow."""

from __future__ import annotations

from decimal import Decimal

import pytest
from ntheemba.application.workflow_router import WorkflowContext
from ntheemba.domain.enums import (
    Flow,
    FulfilmentMethod,
    IntentType,
    MessageRole,
    Stage,
)
from ntheemba.domain.intents import EntitySet, Intent
from ntheemba.domain.order_draft import OrderDraft, PriceSnapshot
from ntheemba.domain.product_resolution import ProductQuery, ProductResolution, ResolvedProduct
from ntheemba.domain.session import Session
from ntheemba.domain.transitions import TransitionPolicy
from ntheemba.ports.ncpc import CanonicalProduct
from ntheemba.ports.tradeflow import BusinessProduct
from ntheemba.services.product_resolver import ProductResolver
from ntheemba.services.response_builder import ResponseBuilder
from ntheemba.workflows.catalogue import CatalogueWorkflow
from ntheemba.workflows.order import (
    OrderStateError,
    OrderWorkflow,
    UnsupportedOrderIntentError,
    build_order_routes,
)
from tests.fakes.ncpc import InMemoryNCPC
from tests.fakes.tradeflow import InMemoryTradeFlow


def _context(
    session: Session,
    intent_type: IntentType,
    *,
    entities: EntitySet | None = None,
    message_id: str = "MSG-1",
) -> WorkflowContext:
    return WorkflowContext(
        session=session,
        intent=Intent(
            type=intent_type,
            role=MessageRole.PENDING_ANSWER,
            confidence=1.0,
            entities=entities or EntitySet(raw_text=intent_type.value),
        ),
        business_id=session.business_id,
        customer_id=session.customer_id,
        request_id="REQ-1",
        message_id=message_id,
    )


def _tradeflow() -> InMemoryTradeFlow:
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
    return tradeflow


def _workflow(
    tradeflow: InMemoryTradeFlow | None = None,
) -> tuple[OrderWorkflow, InMemoryTradeFlow]:
    business = tradeflow or _tradeflow()
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
        resolver=ProductResolver(ncpc=ncpc, tradeflow=business),
        tradeflow=business,
        responses=responses,
    )
    return (
        OrderWorkflow(
            catalogue=catalogue,
            tradeflow=business,
            responses=responses,
        ),
        business,
    )


def _resolved_product(*, shop_id: str = "") -> ResolvedProduct:
    return ResolvedProduct(
        ncpc_product_id="NCPC-500",
        business_product_id="BP-500",
        name="Boom Washing Powder 500g",
        selling_price=Decimal("24"),
        currency="ZMW",
        available=True,
        size_value=Decimal("500"),
        size_unit="g",
        shop_id=shop_id,
    )


def _session_with_selected_catalogue_product() -> Session:
    policy = TransitionPolicy()
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.transition_to(policy, Flow.CATALOGUE, Stage.CATALOGUE_SEARCH)
    session.transition_to(policy, Flow.CATALOGUE, Stage.PRODUCT_SELECTED)
    product = _resolved_product()
    session.product_resolution = ProductResolution.resolved(
        ProductQuery(original_text="Boom 500g"),
        product,
        confidence=1.0,
    )
    return session


def _complete_review_session() -> Session:
    policy = TransitionPolicy()
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.transition_to(policy, Flow.ORDER, Stage.CATALOGUE_SEARCH)
    session.transition_to(policy, Flow.ORDER, Stage.PRODUCT_SELECTED)
    session.transition_to(policy, Flow.ORDER, Stage.QUANTITY)
    session.transition_to(policy, Flow.ORDER, Stage.FULFILMENT_METHOD)
    session.transition_to(policy, Flow.ORDER, Stage.CUSTOMER_DETAILS)
    session.transition_to(policy, Flow.ORDER, Stage.ORDER_REVIEW)
    draft = OrderDraft(product=_resolved_product())
    draft.set_quantity(2)
    draft.set_fulfilment_method(FulfilmentMethod.COLLECTION)
    draft.set_customer("James Chisulo", "0970000000")
    draft.apply_final_validation(
        price=PriceSnapshot(Decimal("24"), "ZMW"),
        availability_confirmed=True,
        validation_reference="review:MSG-1",
    )
    session.order_draft = draft
    return session


@pytest.mark.asyncio
async def test_start_without_product_clue_asks_for_product() -> None:
    workflow, _tradeflow_instance = _workflow()
    session = Session.create("BUS-1", "CUSTOMER-1")

    result = await workflow.handle(
        _context(
            session,
            IntentType.START_ORDER,
            entities=EntitySet(query="I want to order", raw_text="I want to order"),
        )
    )

    assert session.flow == Flow.ORDER
    assert session.stage == Stage.CATALOGUE_SEARCH
    assert session.order_draft is not None
    assert session.pending_question is not None
    assert result.replies[0].metadata["field"] == "product"


@pytest.mark.asyncio
async def test_start_from_selected_catalogue_product_asks_for_quantity() -> None:
    workflow, _tradeflow_instance = _workflow()
    session = _session_with_selected_catalogue_product()

    result = await workflow.handle(_context(session, IntentType.START_ORDER))

    assert session.flow == Flow.ORDER
    assert session.stage == Stage.QUANTITY
    assert session.order_draft is not None
    assert session.order_draft.product == _resolved_product()
    assert result.replies[0].metadata["field"] == "quantity"


@pytest.mark.asyncio
async def test_selected_product_quantity_prompt_repeats_when_quantity_missing() -> None:
    workflow, _tradeflow_instance = _workflow()
    session = _session_with_selected_catalogue_product()
    await workflow.handle(_context(session, IntentType.START_ORDER))

    result = await workflow.handle(
        _context(
            session,
            IntentType.PROVIDE_QUANTITY,
            entities=EntitySet(raw_text="order this"),
        )
    )

    assert session.flow == Flow.ORDER
    assert session.stage == Stage.QUANTITY
    assert session.pending_question is not None
    assert result.replies[0].metadata["field"] == "quantity"
    assert result.events[0].event_type == "order.quantity_missing"


@pytest.mark.asyncio
async def test_combined_start_requires_product_confirmation_before_quantity() -> None:
    workflow, _tradeflow_instance = _workflow()
    session = Session.create("BUS-1", "CUSTOMER-1")

    result = await workflow.handle(
        _context(
            session,
            IntentType.START_ORDER,
            entities=EntitySet(
                query="order 2 Boom 500g",
                quantity=2,
                raw_text="order 2 Boom 500g",
            ),
        )
    )

    assert session.flow == Flow.ORDER
    assert session.stage == Stage.ITEM_SELECTION
    assert session.order_draft is not None
    assert session.order_draft.quantity is None
    assert session.order_draft.price_snapshot is None
    assert session.product_resolution is not None
    assert session.product_resolution.selected is None
    assert result.replies[-1].metadata["response_type"] == "product_suggestion"


@pytest.mark.asyncio
async def test_unavailable_quantity_returns_to_quantity_prompt() -> None:
    workflow, tradeflow = _workflow()
    session = _session_with_selected_catalogue_product()
    await workflow.handle(_context(session, IntentType.START_ORDER))
    tradeflow.products["BUS-1"]["BP-500"] = BusinessProduct(
        business_product_id="BP-500",
        ncpc_product_id="NCPC-500",
        name="Boom Washing Powder 500g",
        selling_price=Decimal("24"),
        currency="ZMW",
        available_quantity=1,
    )

    result = await workflow.handle(
        _context(
            session,
            IntentType.PROVIDE_QUANTITY,
            entities=EntitySet(quantity=2, raw_text="2"),
        )
    )

    assert session.stage == Stage.QUANTITY
    assert session.order_draft is not None
    assert session.order_draft.quantity is None
    assert result.replies[0].metadata["response_type"] == "quantity_unavailable"


@pytest.mark.asyncio
async def test_collection_moves_directly_to_customer_details() -> None:
    workflow, _tradeflow_instance = _workflow()
    session = _session_with_selected_catalogue_product()
    await workflow.handle(_context(session, IntentType.START_ORDER))
    await workflow.handle(
        _context(
            session,
            IntentType.PROVIDE_QUANTITY,
            entities=EntitySet(quantity=2, raw_text="2"),
        )
    )

    result = await workflow.handle(
        _context(
            session,
            IntentType.PROVIDE_FULFILMENT_METHOD,
            entities=EntitySet(
                fulfilment_method=FulfilmentMethod.COLLECTION,
                raw_text="collection",
            ),
        )
    )

    assert session.stage == Stage.CUSTOMER_DETAILS
    assert result.replies[0].metadata["field"] == "customer_name"


@pytest.mark.asyncio
async def test_delivery_requires_delivery_details_before_customer() -> None:
    workflow, _tradeflow_instance = _workflow()
    session = _session_with_selected_catalogue_product()
    await workflow.handle(_context(session, IntentType.START_ORDER))
    await workflow.handle(
        _context(
            session,
            IntentType.PROVIDE_QUANTITY,
            entities=EntitySet(quantity=2, raw_text="2"),
        )
    )

    result = await workflow.handle(
        _context(
            session,
            IntentType.PROVIDE_FULFILMENT_METHOD,
            entities=EntitySet(
                fulfilment_method=FulfilmentMethod.DELIVERY,
                raw_text="delivery",
            ),
        )
    )

    assert session.stage == Stage.DELIVERY_DETAILS
    assert result.replies[0].metadata["field"] == "delivery_details"


@pytest.mark.asyncio
async def test_customer_details_revalidate_and_present_review() -> None:
    workflow, _tradeflow_instance = _workflow()
    session = _session_with_selected_catalogue_product()
    await workflow.handle(_context(session, IntentType.START_ORDER))
    await workflow.handle(
        _context(
            session,
            IntentType.PROVIDE_QUANTITY,
            entities=EntitySet(quantity=2, raw_text="2"),
        )
    )
    await workflow.handle(
        _context(
            session,
            IntentType.PROVIDE_FULFILMENT_METHOD,
            entities=EntitySet(
                fulfilment_method=FulfilmentMethod.COLLECTION,
                raw_text="collection",
            ),
        )
    )

    result = await workflow.handle(
        _context(
            session,
            IntentType.PROVIDE_CUSTOMER_DETAILS,
            entities=EntitySet(
                customer_name="James Chisulo",
                contact_number="0970000000",
                raw_text="James Chisulo 0970000000",
            ),
        )
    )

    assert session.stage == Stage.ORDER_REVIEW
    assert session.order_draft is not None
    assert session.order_draft.ready_for_submission
    assert "Estimated total: K48.00" in (result.replies[0].text or "")


@pytest.mark.asyncio
async def test_price_change_requires_fresh_confirmation() -> None:
    workflow, tradeflow = _workflow()
    session = _complete_review_session()
    tradeflow.products["BUS-1"]["BP-500"] = BusinessProduct(
        business_product_id="BP-500",
        ncpc_product_id="NCPC-500",
        name="Boom Washing Powder 500g",
        selling_price=Decimal("25"),
        currency="ZMW",
        available_quantity=8,
    )

    result = await workflow.handle(_context(session, IntentType.CONFIRM))

    assert session.stage == Stage.ORDER_REVIEW
    assert not tradeflow.orders
    assert result.replies[0].metadata["response_type"] == "order_price_changed"
    assert "K24.00 to K25.00" in (result.replies[0].text or "")


@pytest.mark.asyncio
async def test_second_confirmation_submits_order_idempotently() -> None:
    workflow, tradeflow = _workflow()
    session = _complete_review_session()

    first = await workflow.handle(_context(session, IntentType.CONFIRM, message_id="CONFIRM-1"))
    second = await workflow.handle(_context(session, IntentType.CONFIRM, message_id="CONFIRM-1"))

    assert session.stage == Stage.SUBMITTED
    assert session.order_draft is not None
    assert session.order_draft.submitted
    assert len(tradeflow.orders) == 1
    assert first.replies[0].metadata["created"] is True
    assert second.replies[0].metadata["created"] is False


@pytest.mark.asyncio
async def test_quantity_correction_preserves_other_fields() -> None:
    workflow, _tradeflow_instance = _workflow()
    session = _complete_review_session()

    result = await workflow.handle(
        _context(
            session,
            IntentType.CORRECT,
            entities=EntitySet(raw_text="change quantity", extras={"field": "quantity"}),
        )
    )

    assert session.stage == Stage.QUANTITY
    assert session.order_draft is not None
    assert session.order_draft.quantity is None
    assert session.order_draft.customer_name == "James Chisulo"
    assert result.replies[0].metadata["field"] == "quantity"


@pytest.mark.asyncio
async def test_product_correction_returns_to_order_catalogue_search() -> None:
    workflow, _tradeflow_instance = _workflow()
    session = _complete_review_session()

    await workflow.handle(
        _context(
            session,
            IntentType.CORRECT,
            entities=EntitySet(raw_text="change product", extras={"field": "product"}),
        )
    )

    assert session.flow == Flow.ORDER
    assert session.stage == Stage.CATALOGUE_SEARCH
    assert session.product_resolution is None
    assert session.order_draft is not None
    assert session.order_draft.product is None


@pytest.mark.asyncio
async def test_cancel_clears_order_state() -> None:
    workflow, _tradeflow_instance = _workflow()
    session = _complete_review_session()

    result = await workflow.handle(_context(session, IntentType.CANCEL))

    assert session.flow == Flow.IDLE
    assert session.stage == Stage.CANCELLED
    assert session.order_draft is None
    assert result.replies[0].metadata["response_type"] == "cancelled"


@pytest.mark.asyncio
async def test_unsupported_intent_is_rejected() -> None:
    workflow, _tradeflow_instance = _workflow()
    session = Session.create("BUS-1", "CUSTOMER-1")

    with pytest.raises(UnsupportedOrderIntentError):
        await workflow.handle(_context(session, IntentType.START_BOOKING))


def test_route_helper_registers_order_intents() -> None:
    workflow, _tradeflow_instance = _workflow()

    routes = build_order_routes(workflow)

    assert set(routes) == {
        IntentType.START_ORDER,
        IntentType.PROVIDE_QUANTITY,
        IntentType.PROVIDE_FULFILMENT_METHOD,
        IntentType.PROVIDE_DELIVERY_DETAILS,
        IntentType.PROVIDE_CUSTOMER_DETAILS,
        IntentType.CONFIRM,
        IntentType.CORRECT,
        IntentType.CANCEL,
    }
    assert all(handler is workflow for handler in routes.values())


def test_missing_draft_is_rejected() -> None:
    workflow, _tradeflow_instance = _workflow()
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.flow = Flow.ORDER
    session.stage = Stage.QUANTITY

    with pytest.raises(OrderStateError, match="no draft"):
        workflow._require_draft(session)


@pytest.mark.asyncio
async def test_hidden_product_during_quantity_returns_to_catalogue_search() -> None:
    workflow, tradeflow = _workflow()
    session = _session_with_selected_catalogue_product()
    await workflow.handle(_context(session, IntentType.START_ORDER))
    tradeflow.products["BUS-1"]["BP-500"] = BusinessProduct(
        business_product_id="BP-500",
        ncpc_product_id="NCPC-500",
        name="Boom Washing Powder 500g",
        selling_price=Decimal("24"),
        currency="ZMW",
        available_quantity=8,
        public_visible=False,
    )

    result = await workflow.handle(
        _context(
            session,
            IntentType.PROVIDE_QUANTITY,
            entities=EntitySet(quantity=2, raw_text="2"),
        )
    )

    assert session.stage == Stage.CATALOGUE_SEARCH
    assert session.product_resolution is None
    assert session.order_draft is not None
    assert session.order_draft.product is None
    assert "choose another product" in (result.replies[0].text or "").lower()

@pytest.mark.asyncio
async def test_order_preserves_selected_shop_for_availability_and_submission() -> None:
    workflow, tradeflow = _workflow()
    policy = TransitionPolicy()
    session = Session.create("BUS-1", "CUSTOMER-1")
    session.transition_to(policy, Flow.CATALOGUE, Stage.CATALOGUE_SEARCH)
    session.transition_to(policy, Flow.CATALOGUE, Stage.PRODUCT_SELECTED)
    selected = _resolved_product(shop_id="shop-kitwe")
    session.product_resolution = ProductResolution.resolved(
        ProductQuery(original_text="Boom 500g"),
        selected,
        confidence=1.0,
    )

    await workflow.handle(_context(session, IntentType.START_ORDER))
    await workflow.handle(
        _context(
            session,
            IntentType.PROVIDE_QUANTITY,
            entities=EntitySet(quantity=1, raw_text="1"),
        )
    )

    availability_calls = [
        call for call in tradeflow.calls if call[0] == "check_product_availability"
    ]
    assert availability_calls[-1][1] == ("BUS-1", "BP-500", 1, "shop-kitwe")

    assert session.order_draft is not None
    session.order_draft.set_fulfilment_method(FulfilmentMethod.COLLECTION)
    session.order_draft.set_customer("James Chisulo", "0970000000")
    session.order_draft.apply_final_validation(
        price=PriceSnapshot(Decimal("24"), "ZMW"),
        availability_confirmed=True,
        validation_reference="shop-check",
    )
    request = workflow._submission_request(session.order_draft)
    assert request.shop_id == "shop-kitwe"
