"""Tests for canonical product-resolution models."""

from __future__ import annotations

from decimal import Decimal

import pytest
from ntheemba.domain.enums import ProductResolutionStatus, RelativeSize
from ntheemba.domain.product_resolution import (
    ProductCandidate,
    ProductQuery,
    ProductResolution,
    ResolvedProduct,
)


def test_product_sizes_normalize_for_relative_comparison() -> None:
    five_hundred_grams = ProductCandidate(
        ncpc_product_id="NCPC-500",
        name="Boom 500g",
        size_value=Decimal("500"),
        size_unit="g",
    )
    one_kilogram = ProductCandidate(
        ncpc_product_id="NCPC-1KG",
        name="Boom 1kg",
        size_value=Decimal("1"),
        size_unit="kg",
    )

    assert five_hundred_grams.normalized_size() == ("mass_g", Decimal("500"))
    assert one_kilogram.normalized_size() == ("mass_g", Decimal("1000"))


def test_product_resolution_requires_two_clarification_candidates() -> None:
    query = ProductQuery(original_text="small Boom", relative_size=RelativeSize.SMALL)
    candidate = ProductCandidate(ncpc_product_id="ONE", name="Boom 500g")

    with pytest.raises(ValueError, match="at least two"):
        ProductResolution.needs_clarification(
            query,
            (candidate,),
            confidence=0.6,
            options=("500g",),
        )


def test_resolved_product_resolution_requires_selected_product() -> None:
    query = ProductQuery(original_text="Boom 500g")
    selected = ResolvedProduct(
        ncpc_product_id="NCPC-500",
        business_product_id="BUSPROD-500",
        name="Boom 500g",
        selling_price=Decimal("24"),
        currency="zmw",
        available=True,
    )

    resolution = ProductResolution.resolved(query, selected, confidence=0.98)

    assert resolution.status == ProductResolutionStatus.RESOLVED
    assert resolution.selected is selected
    assert resolution.selected.currency == "ZMW"


def test_one_match_requires_exactly_one_candidate() -> None:
    query = ProductQuery(original_text="Boom")
    first = ProductCandidate(ncpc_product_id="ONE", name="Boom 500g")
    second = ProductCandidate(ncpc_product_id="TWO", name="Boom 1kg")

    with pytest.raises(ValueError, match="exactly one"):
        ProductResolution(
            query=query,
            status=ProductResolutionStatus.ONE_MATCH,
            candidates=(first, second),
            confidence=0.5,
        )


def test_suggestion_places_primary_candidate_first() -> None:
    query = ProductQuery(original_text="small Boom")
    first = ProductCandidate(ncpc_product_id="ONE", name="Boom 500g")
    second = ProductCandidate(ncpc_product_id="TWO", name="Boom 1kg")

    resolution = ProductResolution.suggestion(
        query,
        second,
        confidence=0.8,
        candidates=(first, second),
    )

    assert resolution.status == ProductResolutionStatus.SUGGEST_CONFIRMATION
    assert resolution.candidates == (second, first)
