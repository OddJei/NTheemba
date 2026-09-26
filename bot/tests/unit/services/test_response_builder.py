"""Tests for the central customer-safe response builder."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from ntheemba.application.workflow_router import WorkflowReplyType
from ntheemba.domain.booking_draft import AppointmentSlot, BookingDraft, ServiceSelection
from ntheemba.domain.enums import (
    Flow,
    FulfilmentMethod,
    ProductResolutionOutcome,
    ProductResolutionStatus,
)
from ntheemba.domain.order_draft import OrderDraft, PriceSnapshot
from ntheemba.domain.product_resolution import (
    ProductCandidate,
    ProductQuery,
    ProductResolution,
    ResolvedProduct,
)
from ntheemba.ports.tradeflow import (
    BusinessHours,
    BusinessInformation,
    BusinessProduct,
    FAQAnswer,
    ProductAvailability,
    StaffOption,
    SubmissionResult,
)
from ntheemba.services.response_builder import (
    ResponseBuilder,
    ResponseBuilderConfig,
    ResponseBuilderError,
)


def _resolved_product() -> ResolvedProduct:
    return ResolvedProduct(
        ncpc_product_id="NCPC-500",
        business_product_id="BP-500",
        name="Boom Washing Powder 500g",
        selling_price=Decimal("24"),
        currency="ZMW",
        available=True,
    )


def _complete_order(*, delivery: bool = False) -> OrderDraft:
    draft = OrderDraft()
    draft.select_product(_resolved_product())
    draft.set_quantity(2)
    draft.set_fulfilment_method(
        FulfilmentMethod.DELIVERY if delivery else FulfilmentMethod.COLLECTION
    )
    if delivery:
        draft.set_delivery_details("House 12, near the blue water tank")
    draft.set_customer("James Chisulo", "0970000000")
    draft.apply_final_validation(
        price=PriceSnapshot(Decimal("24"), "ZMW"),
        availability_confirmed=True,
        validation_reference="VAL-1",
    )
    return draft


def _complete_booking() -> BookingDraft:
    service = ServiceSelection(
        service_id="SVC-1",
        name="Knotless Braids",
        duration_minutes=180,
        price=Decimal("350"),
        currency="ZMW",
    )
    slot = AppointmentSlot(
        slot_id="SLOT-1",
        service_id="SVC-1",
        appointment_date=date(2026, 7, 25),
        start_time=time(9, 0),
        end_time=time(12, 0),
        staff_id="STAFF-1",
        staff_name="Mary",
    )
    draft = BookingDraft()
    draft.select_service(service)
    draft.set_preferred_date(date(2026, 7, 25))
    draft.select_slot(slot)
    draft.set_customer("Jane", "0971111111")
    draft.apply_final_validation(slot_confirmed=True, validation_reference="BVAL-1")
    return draft


def test_business_information_contains_only_public_fields() -> None:
    reply = ResponseBuilder().business_information(
        BusinessInformation(
            business_id="BUS-INTERNAL",
            name="Harvest Big Shop",
            description="Groceries and household products",
            location="Mufulira",
            contact_phone="0970000000",
        )
    )

    assert reply.kind == WorkflowReplyType.TEXT
    assert reply.text is not None
    assert "Harvest Big Shop" in reply.text
    assert "BUS-INTERNAL" not in reply.text


def test_special_closure_includes_date_and_note() -> None:
    reply = ResponseBuilder().business_hours(
        BusinessHours(
            is_open=False,
            local_date=date(2026, 7, 25),
            special_closure=True,
            note="Closed for stocktaking.",
        )
    )

    assert reply.text == "The business is closed on 25 Jul 2026. Closed for stocktaking."


def test_faq_answer_removes_control_characters() -> None:
    reply = ResponseBuilder().faq_answer(
        FAQAnswer(
            faq_id="FAQ-1",
            question="Do you deliver?",
            answer="Yes.\x00 Delivery is available.",
        )
    )

    assert reply.text == "Yes. Delivery is available."


def test_product_results_never_expose_internal_ids() -> None:
    product = BusinessProduct(
        business_product_id="BP-SECRET",
        ncpc_product_id="NCPC-SECRET",
        name="Boom 500g",
        selling_price=Decimal("24"),
        currency="ZMW",
        available_quantity=8,
    )

    reply = ResponseBuilder().product_results((product,))

    assert reply.text is not None
    assert "K24.00" in reply.text
    assert "BP-SECRET" not in reply.text
    assert "NCPC-SECRET" not in reply.text


def test_product_results_hide_non_public_products() -> None:
    hidden = BusinessProduct(
        business_product_id="BP-1",
        ncpc_product_id="NCPC-1",
        name="Hidden Product",
        selling_price=Decimal("10"),
        currency="ZMW",
        available_quantity=5,
        public_visible=False,
    )

    reply = ResponseBuilder().product_results((hidden,))

    assert reply.metadata["response_type"] == "catalogue_no_match"


def test_product_detail_builds_image_then_text() -> None:
    product = BusinessProduct(
        business_product_id="BP-1",
        ncpc_product_id="NCPC-1",
        name="Boom 500g",
        selling_price=Decimal("24"),
        currency="ZMW",
        available_quantity=5,
        image_url="https://example.test/boom.jpg",
    )

    replies = ResponseBuilder().product_detail(product)

    assert [reply.kind for reply in replies] == [
        WorkflowReplyType.IMAGE,
        WorkflowReplyType.TEXT,
    ]
    assert replies[0].caption is not None
    assert "K24.00" in replies[0].caption


def test_product_detail_rejects_non_http_public_image() -> None:
    product = BusinessProduct(
        business_product_id="BP-1",
        ncpc_product_id="NCPC-1",
        name="Boom 500g",
        selling_price=Decimal("24"),
        currency="ZMW",
        available_quantity=5,
        image_url="file:///secret.jpg",
    )

    with pytest.raises(ResponseBuilderError, match="HTTP"):
        ResponseBuilder().product_detail(product)


def test_service_results_include_duration_and_price() -> None:
    reply = ResponseBuilder().service_results(
        (
            ServiceSelection(
                service_id="SVC-1",
                name="Knotless Braids",
                duration_minutes=180,
                price=Decimal("350"),
                currency="ZMW",
            ),
        )
    )

    assert reply.text is not None
    assert "180 minutes" in reply.text
    assert "K350.00" in reply.text
    assert "SVC-1" not in reply.text


def test_product_clarification_numbers_options_without_ids() -> None:
    candidates = (
        ProductCandidate(
            ncpc_product_id="NCPC-500",
            name="Boom 500g",
            business_product_id="BP-500",
            selling_price=Decimal("24"),
            currency="ZMW",
        ),
        ProductCandidate(
            ncpc_product_id="NCPC-1KG",
            name="Boom 1kg",
            business_product_id="BP-1KG",
            selling_price=Decimal("42"),
            currency="ZMW",
        ),
    )
    resolution = ProductResolution(
        query=ProductQuery(original_text="small Boom"),
        status=ProductResolutionStatus.NEEDS_CLARIFICATION,
        candidates=candidates,
        confidence=0.7,
        clarification_options=("500g", "1kg"),
    )

    reply = ResponseBuilder().product_clarification(resolution)

    assert reply.text is not None
    assert "1. 500g" in reply.text
    assert "2. 1kg" in reply.text
    assert "BP-500" not in reply.text


def test_quantity_unavailable_returns_live_available_quantity() -> None:
    reply = ResponseBuilder().quantity_unavailable(
        ProductAvailability(
            business_product_id="BP-500",
            requested_quantity=4,
            available_quantity=2,
            selling_price=Decimal("24"),
            currency="ZMW",
        )
    )

    assert reply.text is not None
    assert "2" in reply.text
    assert "BP-500" not in reply.text


def test_available_slots_and_staff_do_not_expose_ids() -> None:
    builder = ResponseBuilder()
    slot_reply = builder.available_slots(
        (
            AppointmentSlot(
                slot_id="SLOT-SECRET",
                service_id="SVC-SECRET",
                appointment_date=date(2026, 7, 25),
                start_time=time(9, 0),
                end_time=time(12, 0),
                staff_id="STAFF-SECRET",
                staff_name="Mary",
            ),
        )
    )
    staff_reply = builder.staff_options((StaffOption("STAFF-SECRET", "Mary"),))

    assert slot_reply.text is not None
    assert staff_reply.text is not None
    assert "SLOT-SECRET" not in slot_reply.text
    assert "STAFF-SECRET" not in slot_reply.text
    assert "STAFF-SECRET" not in staff_reply.text


def test_order_review_contains_total_and_no_validation_reference() -> None:
    reply = ResponseBuilder().order_review(_complete_order(delivery=True))

    assert reply.text is not None
    assert "Estimated total: K48.00" in reply.text
    assert "House 12" in reply.text
    assert "VAL-1" not in reply.text


def test_order_review_rejects_incomplete_draft() -> None:
    with pytest.raises(ResponseBuilderError, match="complete draft"):
        ResponseBuilder().order_review(OrderDraft())


def test_booking_review_uses_human_date_and_time() -> None:
    reply = ResponseBuilder().booking_review(_complete_booking())

    assert reply.text is not None
    assert "25 Jul 2026" in reply.text
    assert "09:00-12:00" in reply.text
    assert "Mary" in reply.text
    assert "BVAL-1" not in reply.text


def test_submission_responses_explain_no_payment() -> None:
    builder = ResponseBuilder()
    result = SubmissionResult("ORD-123", "pending_business_confirmation", True)

    order_reply = builder.order_submitted(result)
    booking_reply = builder.booking_submitted(result)

    assert order_reply.text is not None
    assert booking_reply.text is not None
    assert "No payment has been taken" in order_reply.text
    assert "No payment has been taken" in booking_reply.text


def test_correction_prompt_is_flow_specific() -> None:
    builder = ResponseBuilder()

    order = builder.correction_prompt(Flow.ORDER, "quantity")
    booking = builder.correction_prompt(Flow.BOOKING, "selected_slot")

    assert order.text == "What quantity would you like instead?"
    assert booking.text == "Choose another available time."


def test_dependency_failure_distinguishes_retryability() -> None:
    builder = ResponseBuilder()

    retryable = builder.dependency_failure(retryable=True, action_name="your order")
    final = builder.dependency_failure(retryable=False, action_name="your order")

    assert retryable.text is not None
    assert final.text is not None
    assert "temporarily unavailable" in retryable.text
    assert "check the details" in final.text


def test_each_product_resolution_outcome_has_deterministic_customer_response() -> None:
    builder = ResponseBuilder()

    replies = {
        outcome: builder.product_resolution_failure(outcome)
        for outcome in ProductResolutionOutcome
    }

    assert set(replies) == set(ProductResolutionOutcome)
    assert len({reply.text for reply in replies.values()}) == len(ProductResolutionOutcome)
    for outcome, reply in replies.items():
        assert reply.text
        assert reply.metadata["response_type"] == "product_resolution_failure"
        assert reply.metadata["outcome"] == outcome.value
        assert "token" not in reply.text.lower()
        assert "credential" not in reply.text.lower()


def test_unknown_currency_uses_three_letter_code() -> None:
    assert ResponseBuilder().format_money(Decimal("12.5"), "BWP") == "BWP 12.50"


def test_config_limits_catalogue_results_and_response_length() -> None:
    builder = ResponseBuilder(ResponseBuilderConfig(max_catalogue_items=1, max_text_length=200))
    products = (
        BusinessProduct("BP-1", "N-1", "One", Decimal("1"), "ZMW", 1),
        BusinessProduct("BP-2", "N-2", "Two", Decimal("2"), "ZMW", 1),
    )

    reply = builder.product_results(products)

    assert reply.text is not None
    assert "1. One" in reply.text
    assert "2. Two" not in reply.text
    assert "Showing the first 1" in reply.text


def test_workflow_resumed_repeats_sanitized_pending_question() -> None:
    builder = ResponseBuilder()

    reply = builder.workflow_resumed("  How many\t would you like?  ")

    assert reply.text == "Back to your previous request: How many would you like?"
    assert reply.metadata["response_type"] == "workflow_resumed"


def test_conversation_closed_uses_safe_restart_wording() -> None:
    builder = ResponseBuilder()

    reply = builder.conversation_closed()

    assert reply.text == (
        "This conversation has been closed. Send a new message whenever you need help again."
    )
    assert reply.metadata["response_type"] == "conversation_closed"


def test_price_changed_order_review_requires_new_confirmation() -> None:
    builder = ResponseBuilder()
    draft = OrderDraft(product=_resolved_product())
    draft.set_quantity(2)
    draft.set_fulfilment_method(FulfilmentMethod.COLLECTION)
    draft.set_customer("James Chisulo", "0970000000")
    draft.apply_final_validation(
        price=PriceSnapshot(Decimal("25"), "ZMW"),
        availability_confirmed=True,
        validation_reference="CONFIRM-2",
    )

    reply = builder.price_changed_order_review(
        draft,
        previous_amount=Decimal("24"),
        previous_currency="ZMW",
    )

    assert reply.metadata["response_type"] == "order_price_changed"
    assert "K24.00 to K25.00" in (reply.text or "")
    assert "Reply CONFIRM" in (reply.text or "")
