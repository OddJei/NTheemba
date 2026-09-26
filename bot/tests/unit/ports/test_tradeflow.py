"""Tests for the in-memory TradeFlow port."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from ntheemba.domain.booking_draft import AppointmentSlot, ServiceSelection
from ntheemba.domain.enums import FulfilmentMethod
from ntheemba.ports.tradeflow import (
    BusinessProduct,
    OrderSubmissionRequest,
)
from tests.fakes.tradeflow import InMemoryTradeFlow


@pytest.mark.asyncio
async def test_tradeflow_filters_ncpc_candidates_to_business_catalogue() -> None:
    tradeflow = InMemoryTradeFlow()
    tradeflow.products["BUS-1"] = {
        "BP-500": BusinessProduct(
            business_product_id="BP-500",
            ncpc_product_id="NCPC-500",
            name="Boom 500g",
            selling_price=Decimal("24"),
            currency="ZMW",
            available_quantity=8,
        ),
        "BP-HIDDEN": BusinessProduct(
            business_product_id="BP-HIDDEN",
            ncpc_product_id="NCPC-1KG",
            name="Boom 1kg",
            selling_price=Decimal("42"),
            currency="ZMW",
            available_quantity=5,
            public_visible=False,
        ),
    }

    products = await tradeflow.filter_business_products(
        "BUS-1",
        ("NCPC-500", "NCPC-1KG"),
    )

    assert [product.business_product_id for product in products] == ["BP-500"]


@pytest.mark.asyncio
async def test_tradeflow_availability_uses_live_quantity() -> None:
    tradeflow = InMemoryTradeFlow()
    tradeflow.products["BUS-1"] = {
        "BP-500": BusinessProduct(
            business_product_id="BP-500",
            ncpc_product_id="NCPC-500",
            name="Boom 500g",
            selling_price=Decimal("24"),
            currency="ZMW",
            available_quantity=1,
        )
    }

    availability = await tradeflow.check_product_availability(
        "BUS-1",
        "BP-500",
        quantity=2,
    )

    assert not availability.available
    assert availability.available_quantity == 1


@pytest.mark.asyncio
async def test_order_submission_is_idempotent() -> None:
    tradeflow = InMemoryTradeFlow()
    request = OrderSubmissionRequest(
        business_product_id="BP-500",
        quantity=2,
        fulfilment_method=FulfilmentMethod.COLLECTION,
        customer_name="James",
        contact_number="260970000001",
    )

    first = await tradeflow.create_order_request(
        "BUS-1",
        request,
        idempotency_key="CONV-1:MSG-1:order",
    )
    second = await tradeflow.create_order_request(
        "BUS-1",
        request,
        idempotency_key="CONV-1:MSG-1:order",
    )

    assert first.created
    assert not second.created
    assert second.request_id == first.request_id


@pytest.mark.asyncio
async def test_tradeflow_returns_seeded_booking_slots() -> None:
    tradeflow = InMemoryTradeFlow()
    appointment_date = date(2026, 7, 25)
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
        appointment_date=appointment_date,
        start_time=time(9, 0),
        end_time=time(12, 0),
        staff_id="STAFF-1",
    )
    tradeflow.services["BUS-1"] = {service.service_id: service}
    tradeflow.slots[("BUS-1", "SVC-1", appointment_date)] = (slot,)

    slots = await tradeflow.get_available_slots(
        "BUS-1",
        "SVC-1",
        appointment_date=appointment_date,
    )

    assert slots == (slot,)
