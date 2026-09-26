"""Tests for order draft completeness and final validation."""

from __future__ import annotations

from decimal import Decimal

import pytest
from ntheemba.domain.enums import FulfilmentMethod
from ntheemba.domain.order_draft import OrderDraft, PriceSnapshot
from ntheemba.domain.product_resolution import ResolvedProduct


def _product() -> ResolvedProduct:
    return ResolvedProduct(
        ncpc_product_id="NCPC-500",
        business_product_id="BUSPROD-500",
        name="Boom Washing Powder 500g",
        selling_price=Decimal("24"),
        currency="ZMW",
        available=True,
    )


def test_delivery_order_requires_delivery_details() -> None:
    draft = OrderDraft()
    draft.select_product(_product())
    draft.set_quantity(2)
    draft.set_fulfilment_method(FulfilmentMethod.DELIVERY)
    draft.set_customer("James", "260970000000")

    assert draft.missing_fields() == ("delivery_details",)
    assert not draft.ready_for_review


def test_collection_order_can_be_reviewed_without_address() -> None:
    draft = OrderDraft()
    draft.select_product(_product())
    draft.set_quantity(2)
    draft.set_fulfilment_method(FulfilmentMethod.COLLECTION)
    draft.set_customer("James", "260970000000")

    assert draft.ready_for_review
    assert not draft.ready_for_submission


def test_final_validation_makes_order_ready_for_submission() -> None:
    draft = OrderDraft()
    draft.select_product(_product())
    draft.set_quantity(2)
    draft.set_fulfilment_method(FulfilmentMethod.COLLECTION)
    draft.set_customer("James", "260970000000")
    draft.apply_final_validation(
        price=PriceSnapshot(amount=Decimal("24"), currency="ZMW"),
        availability_confirmed=True,
        validation_reference="VAL-001",
    )

    assert draft.ready_for_submission
    assert draft.total_price == Decimal("48")


def test_mutation_invalidates_validation_and_submission_state() -> None:
    draft = OrderDraft(product=_product())
    draft.set_quantity(2)
    draft.set_fulfilment_method(FulfilmentMethod.COLLECTION)
    draft.set_customer("James", "260970000000")
    draft.apply_final_validation(
        price=PriceSnapshot(Decimal("24"), "ZMW"),
        availability_confirmed=True,
        validation_reference="VAL-1",
    )
    draft.mark_submitted("ORD-1", "pending")

    draft.set_quantity(3)

    assert draft.price_snapshot is None
    assert not draft.availability_confirmed
    assert draft.validation_reference is None
    assert not draft.submitted


def test_submission_requires_validated_complete_draft() -> None:
    draft = OrderDraft(product=_product())

    with pytest.raises(ValueError, match="ready for submission"):
        draft.mark_submitted("ORD-1", "pending")
