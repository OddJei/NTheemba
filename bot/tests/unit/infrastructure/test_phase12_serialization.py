"""Tests for versioned durable-session serialization."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest
from ntheemba.domain.booking_draft import AppointmentSlot, BookingDraft, ServiceSelection
from ntheemba.domain.enums import Flow, FulfilmentMethod, IntentType, Stage
from ntheemba.domain.intents import PendingQuestion
from ntheemba.domain.order_draft import OrderDraft, PriceSnapshot
from ntheemba.domain.product_resolution import ProductQuery, ProductResolution, ResolvedProduct
from ntheemba.domain.session import ConversationTurn, Session, SuspendedState
from ntheemba.infrastructure.serialization import (
    SESSION_CODEC,
    SerializationError,
    decode_session,
    encode_session,
)


def _complex_session() -> Session:
    now = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
    product = ResolvedProduct(
        ncpc_product_id="NCPC-1",
        business_product_id="PROD-1",
        name="Cooking Oil 2L",
        selling_price=Decimal("125.50"),
        currency="ZMW",
        available=True,
        size_value=Decimal("2"),
        size_unit="l",
    )
    order = OrderDraft(
        product=product,
        quantity=2,
        fulfilment_method=FulfilmentMethod.DELIVERY,
        delivery_details="Mufulira Central",
        customer_name="James",
        contact_number="+260971234567",
        price_snapshot=PriceSnapshot(Decimal("125.50"), "ZMW"),
        availability_confirmed=True,
        validation_reference="VALID-1",
    )
    booking = BookingDraft(
        service=ServiceSelection("SERVICE-1", "Braiding", 120, Decimal("250"), "ZMW"),
        preferred_date=date(2026, 8, 3),
        selected_slot=AppointmentSlot(
            "SLOT-1",
            "SERVICE-1",
            date(2026, 8, 3),
            time(9, 0),
            time(11, 0),
        ),
        customer_name="James",
        contact_number="+260971234567",
    )
    query = ProductQuery(original_text="2 litre cooking oil")
    resolution = ProductResolution.resolved(query, product, confidence=0.98)
    question = PendingQuestion(
        "Collection or delivery?",
        frozenset({IntentType.PROVIDE_FULFILMENT_METHOD}),
        metadata={"field": "fulfilment"},
        created_at=now,
    )
    return Session(
        conversation_id="CONV-1",
        business_id="harvest",
        customer_id="+260971234567",
        flow=Flow.ORDER,
        stage=Stage.CUSTOMER_CONFIRMATION,
        order_draft=order,
        booking_draft=booking,
        product_resolution=resolution,
        pending_question=question,
        suspended_state=SuspendedState(Flow.ORDER, Stage.QUANTITY, question),
        recent_history=[ConversationTurn("customer", "I want two", "MSG-1", now)],
        conversation_summary="Customer is ordering cooking oil.",
        revision=4,
        started_at=now,
        last_activity_at=now,
        expires_at=now + timedelta(hours=24),
    )


def test_session_codec_round_trips_all_nested_runtime_state() -> None:
    session = _complex_session()

    restored = decode_session(encode_session(session))

    assert restored == session
    assert restored.order_draft is not None
    assert restored.order_draft.total_price == Decimal("251.00")
    assert restored.pending_question is not None
    assert restored.pending_question.metadata["field"] == "fulfilment"
    assert restored.flow is Flow.ORDER
    assert restored.stage is Stage.CUSTOMER_CONFIRMATION
    assert restored.order_draft.fulfilment_method is FulfilmentMethod.DELIVERY
    assert restored.pending_question.expected_intents == frozenset(
        {IntentType.PROVIDE_FULFILMENT_METHOD}
    )


def test_session_codec_decodes_legacy_str_enum_payloads() -> None:
    envelope = json.loads(encode_session(_complex_session()))

    def untag_enums(value: object) -> object:
        if isinstance(value, dict):
            if value.get("$type") == "enum":
                return value["value"]
            return {key: untag_enums(item) for key, item in value.items()}
        if isinstance(value, list):
            return [untag_enums(item) for item in value]
        return value

    restored = decode_session(json.dumps(untag_enums(envelope)))

    assert restored.flow is Flow.ORDER
    assert restored.stage is Stage.CUSTOMER_CONFIRMATION
    assert restored.order_draft is not None
    assert restored.order_draft.fulfilment_method is FulfilmentMethod.DELIVERY
    assert restored.pending_question is not None
    assert restored.pending_question.expected_intents == frozenset(
        {IntentType.PROVIDE_FULFILMENT_METHOD}
    )


def test_session_codec_is_deterministic() -> None:
    session = _complex_session()

    assert encode_session(session) == encode_session(session)


def test_session_codec_rejects_wrong_schema() -> None:
    payload = encode_session(_complex_session()).replace(
        b'"ntheemba.session"',
        b'"another.schema"',
    )

    with pytest.raises(SerializationError, match="schema"):
        decode_session(payload)


def test_session_codec_rejects_future_version() -> None:
    payload = encode_session(_complex_session()).replace(b'"version":1', b'"version":99')

    with pytest.raises(SerializationError, match="version"):
        decode_session(payload)


def test_codec_rejects_unlisted_dataclass() -> None:
    from dataclasses import dataclass

    @dataclass
    class Unsafe:
        command: str

    with pytest.raises(SerializationError, match="not allow-listed"):
        SESSION_CODEC.dumps(Unsafe("delete everything"))
