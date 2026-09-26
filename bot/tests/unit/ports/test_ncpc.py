"""Tests for the in-memory NCPC port."""

from __future__ import annotations

from decimal import Decimal

import pytest
from ntheemba.domain.enums import RelativeSize
from ntheemba.domain.product_resolution import ProductQuery
from ntheemba.ports.ncpc import CanonicalProduct
from tests.fakes.ncpc import InMemoryNCPC


@pytest.fixture
def ncpc() -> InMemoryNCPC:
    return InMemoryNCPC(
        (
            CanonicalProduct(
                product_id="NCPC-BOOM-500",
                canonical_name="Boom Washing Powder 500g",
                brand="Boom",
                product_family="Washing Powder",
                size_value=Decimal("500"),
                size_unit="g",
                barcode="600100000001",
                aliases=("Boom small",),
            ),
            CanonicalProduct(
                product_id="NCPC-BOOM-1KG",
                canonical_name="Boom Washing Powder 1kg",
                brand="Boom",
                product_family="Washing Powder",
                size_value=Decimal("1"),
                size_unit="kg",
                barcode="600100000002",
            ),
        )
    )


@pytest.mark.asyncio
async def test_search_returns_canonical_candidates(ncpc: InMemoryNCPC) -> None:
    results = await ncpc.search_products(
        ProductQuery(
            original_text="small Boom",
            brand="Boom",
            relative_size=RelativeSize.SMALL,
        )
    )

    assert {item.product_id for item in results} == {
        "NCPC-BOOM-500",
        "NCPC-BOOM-1KG",
    }


@pytest.mark.asyncio
async def test_barcode_resolves_exact_product(ncpc: InMemoryNCPC) -> None:
    product = await ncpc.resolve_barcode("600100000002")

    assert product is not None
    assert product.product_id == "NCPC-BOOM-1KG"
