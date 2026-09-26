"""Tests for NCPC and TradeFlow-backed product resolution."""

from __future__ import annotations

from decimal import Decimal

import pytest
from ntheemba.domain.enums import (
    ProductResolutionOutcome,
    ProductResolutionStatus,
    RelativeSize,
)
from ntheemba.domain.intents import EntitySet
from ntheemba.domain.product_resolution import ProductQuery
from ntheemba.ports.ncpc import CanonicalProduct
from ntheemba.ports.tradeflow import BusinessProduct
from ntheemba.services.product_resolver import (
    ProductResolutionDependencyError,
    ProductResolver,
    ProductResolverConfig,
    ProductSelectionError,
    product_query_from_entities,
)
from tests.fakes.ncpc import InMemoryNCPC
from tests.fakes.tradeflow import InMemoryTradeFlow


def _canonical_products() -> tuple[CanonicalProduct, ...]:
    return (
        CanonicalProduct(
            product_id="NCPC-BOOM-250",
            canonical_name="Boom Washing Powder 250g",
            brand="Boom",
            product_family="Washing Powder",
            size_value=Decimal("250"),
            size_unit="g",
            barcode="600100000250",
            aliases=("Boom small packet",),
        ),
        CanonicalProduct(
            product_id="NCPC-BOOM-500",
            canonical_name="Boom Washing Powder 500g",
            brand="Boom",
            product_family="Washing Powder",
            size_value=Decimal("500"),
            size_unit="g",
            barcode="600100000500",
        ),
        CanonicalProduct(
            product_id="NCPC-BOOM-1KG",
            canonical_name="Boom Washing Powder 1kg",
            brand="Boom",
            product_family="Washing Powder",
            size_value=Decimal("1"),
            size_unit="kg",
            barcode="600100001000",
        ),
        CanonicalProduct(
            product_id="NCPC-SUGAR-1KG",
            canonical_name="White Sugar 1kg",
            product_family="Sugar",
            size_value=Decimal("1"),
            size_unit="kg",
            barcode="600200001000",
        ),
    )


def _tradeflow() -> InMemoryTradeFlow:
    tradeflow = InMemoryTradeFlow()
    tradeflow.products["BUS-1"] = {
        "BP-BOOM-250": BusinessProduct(
            business_product_id="BP-BOOM-250",
            ncpc_product_id="NCPC-BOOM-250",
            name="Boom Washing Powder 250g",
            selling_price=Decimal("15"),
            currency="ZMW",
            available_quantity=0,
        ),
        "BP-BOOM-500": BusinessProduct(
            business_product_id="BP-BOOM-500",
            ncpc_product_id="NCPC-BOOM-500",
            name="Boom Washing Powder 500g",
            selling_price=Decimal("24"),
            currency="ZMW",
            available_quantity=8,
        ),
        "BP-BOOM-1KG": BusinessProduct(
            business_product_id="BP-BOOM-1KG",
            ncpc_product_id="NCPC-BOOM-1KG",
            name="Boom Washing Powder 1kg",
            selling_price=Decimal("42"),
            currency="ZMW",
            available_quantity=4,
        ),
        "BP-SUGAR-HIDDEN": BusinessProduct(
            business_product_id="BP-SUGAR-HIDDEN",
            ncpc_product_id="NCPC-SUGAR-1KG",
            name="White Sugar 1kg",
            selling_price=Decimal("30"),
            currency="ZMW",
            available_quantity=10,
            public_visible=False,
        ),
    }
    return tradeflow


def _resolver(
    *,
    tradeflow: InMemoryTradeFlow | None = None,
) -> ProductResolver:
    return ProductResolver(
        ncpc=InMemoryNCPC(_canonical_products()),
        tradeflow=tradeflow or _tradeflow(),
        config=ProductResolverConfig(
            ncpc_search_limit=20,
            max_candidates=6,
            suggestion_threshold=0.70,
            exact_match_threshold=0.90,
            dominance_gap=0.12,
        ),
    )


class FailingNCPC(InMemoryNCPC):
    def __init__(self, error: Exception) -> None:
        super().__init__(_canonical_products())
        self.error = error

    async def search_products(
        self,
        query: ProductQuery,
        *,
        limit: int = 20,
    ) -> tuple[CanonicalProduct, ...]:
        raise self.error


class FuzzyNCPC(InMemoryNCPC):
    async def search_products(
        self,
        query: ProductQuery,
        *,
        limit: int = 20,
    ) -> tuple[CanonicalProduct, ...]:
        self.calls.append(("search_products", query))
        return tuple(self.products.values())[:limit]


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


@pytest.mark.asyncio
async def test_exact_barcode_returns_confirmable_business_product() -> None:
    resolution = await _resolver().resolve(
        "BUS-1",
        ProductQuery(
            original_text="",
            barcode="600100000500",
        ),
    )

    assert resolution.status == ProductResolutionStatus.ONE_MATCH
    assert resolution.selected is None
    assert resolution.candidates[0].business_product_id == "BP-BOOM-500"
    assert resolution.candidates[0].selling_price == Decimal("24")
    assert resolution.candidates[0].available


@pytest.mark.asyncio
async def test_barcode_not_sold_by_business_returns_no_match() -> None:
    resolution = await _resolver().resolve(
        "BUS-1",
        ProductQuery(
            original_text="",
            barcode="600200001000",
        ),
    )

    assert resolution.status == ProductResolutionStatus.NO_MATCH
    assert resolution.selected is None
    assert resolution.outcome == ProductResolutionOutcome.SHOP_NO_MATCH


@pytest.mark.asyncio
async def test_ncpc_no_match_records_ncpc_outcome() -> None:
    resolution = await _resolver().resolve(
        "BUS-1",
        ProductQuery(original_text="Unicorn cereal"),
    )

    assert resolution.status == ProductResolutionStatus.NO_MATCH
    assert resolution.outcome == ProductResolutionOutcome.NCPC_NO_MATCH


@pytest.mark.asyncio
async def test_tradeflow_shop_filter_empty_records_shop_no_match() -> None:
    tradeflow = _tradeflow()
    tradeflow.products["BUS-1"] = {}

    resolution = await _resolver(tradeflow=tradeflow).resolve(
        "BUS-1",
        ProductQuery(original_text="Boom", brand="Boom"),
    )

    assert resolution.status == ProductResolutionStatus.NO_MATCH
    assert resolution.outcome == ProductResolutionOutcome.SHOP_NO_MATCH


@pytest.mark.asyncio
async def test_unmapped_ncpc_candidates_fall_back_to_tenant_tradeflow_catalogue() -> None:
    tradeflow = InMemoryTradeFlow()
    tradeflow.products["BUS-1"] = {
        "1001": BusinessProduct(
            business_product_id="1001",
            ncpc_product_id=None,
            ncpc_variant_id=None,
            name="Anjoy Flavoured Drink",
            selling_price=Decimal("1"),
            currency="ZMW",
            available_quantity=1,
            barcode="6009644921652",
            identity_status="awaiting_ncpc_review",
            shop_id="shop-main",
        )
    }
    resolver = ProductResolver(
        ncpc=FuzzyNCPC(_canonical_products()),
        tradeflow=tradeflow,
    )

    resolution = await resolver.resolve(
        "BUS-1",
        ProductQuery(original_text="Anjoy"),
    )

    assert resolution.status == ProductResolutionStatus.ONE_MATCH
    assert resolution.outcome is None
    assert resolution.candidates[0].business_product_id == "1001"
    assert resolution.candidates[0].trusted_identity is False
    assert tradeflow.calls == [
        (
            "filter_business_products",
            (
                "BUS-1",
                (
                    "NCPC-BOOM-250",
                    "NCPC-BOOM-500",
                    "NCPC-BOOM-1KG",
                    "NCPC-SUGAR-1KG",
                ),
            ),
        ),
        ("search_business_products", ("BUS-1", "Anjoy")),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "outcome", "retryable"),
    (
        (TimeoutError("secret endpoint timed out"), ProductResolutionOutcome.NCPC_TIMEOUT, True),
        (PermissionError("token rejected"), ProductResolutionOutcome.AUTH_FAILURE, False),
        (
            ValueError("raw payload included private data"),
            ProductResolutionOutcome.MALFORMED_RESPONSE,
            False,
        ),
    ),
)
async def test_ncpc_dependency_failures_are_stable_and_redacted(
    error: Exception,
    outcome: ProductResolutionOutcome,
    retryable: bool,
) -> None:
    resolver = ProductResolver(ncpc=FailingNCPC(error), tradeflow=_tradeflow())

    with pytest.raises(ProductResolutionDependencyError) as raised:
        await resolver.resolve("BUS-1", ProductQuery(original_text="Boom"))

    assert raised.value.outcome == outcome
    assert raised.value.dependency == "ncpc"
    assert raised.value.retryable is retryable
    assert str(raised.value) == outcome.value


@pytest.mark.asyncio
async def test_tradeflow_timeout_is_classified_without_candidate_leakage() -> None:
    resolver = ProductResolver(
        ncpc=InMemoryNCPC(_canonical_products()),
        tradeflow=FailingTradeFlow(TimeoutError("sheet url")),
    )

    with pytest.raises(ProductResolutionDependencyError) as raised:
        await resolver.resolve("BUS-1", ProductQuery(original_text="Boom"))

    assert raised.value.outcome == ProductResolutionOutcome.TRADEFLOW_TIMEOUT
    assert raised.value.dependency == "tradeflow"
    assert raised.value.retryable is True
    assert "sheet url" not in str(raised.value)


@pytest.mark.asyncio
async def test_explicit_size_and_product_identity_still_requires_confirmation() -> None:
    resolution = await _resolver().resolve(
        "BUS-1",
        ProductQuery(
            original_text="Boom Washing Powder 500g",
            brand="Boom",
            product_family="Washing Powder",
            size_value=Decimal("500"),
            size_unit="g",
        ),
    )

    assert resolution.status == ProductResolutionStatus.NEEDS_CLARIFICATION
    assert resolution.selected is None
    assert resolution.candidates[0].business_product_id == "BP-BOOM-500"


@pytest.mark.asyncio
async def test_broad_brand_query_requires_controlled_clarification() -> None:
    resolution = await _resolver().resolve(
        "BUS-1",
        ProductQuery(
            original_text="Boom",
            brand="Boom",
        ),
    )

    assert resolution.status == ProductResolutionStatus.NEEDS_CLARIFICATION
    assert len(resolution.candidates) == 3
    assert resolution.clarification_options == (
        "Boom Washing Powder 250g (ZMW 15.00, currently unavailable)",
        "Boom Washing Powder 500g (ZMW 24.00, available)",
        "Boom Washing Powder 1kg (ZMW 42.00, available)",
    )
    assert all("BP-" not in option for option in resolution.clarification_options)


@pytest.mark.asyncio
async def test_small_relative_request_orders_smallest_candidate_first() -> None:
    resolution = await _resolver().resolve(
        "BUS-1",
        ProductQuery(
            original_text="small Boom",
            brand="Boom",
            relative_size=RelativeSize.SMALL,
        ),
    )

    assert resolution.status == ProductResolutionStatus.NEEDS_CLARIFICATION
    assert resolution.candidates[0].name == "Boom Washing Powder 250g"


@pytest.mark.asyncio
async def test_smallest_relative_request_still_requires_confirmation() -> None:
    resolution = await _resolver().resolve(
        "BUS-1",
        ProductQuery(
            original_text="smallest Boom",
            brand="Boom",
            relative_size=RelativeSize.SMALLEST,
        ),
    )

    assert resolution.status == ProductResolutionStatus.NEEDS_CLARIFICATION
    assert resolution.selected is None
    assert resolution.candidates[0].business_product_id == "BP-BOOM-250"
    assert not resolution.candidates[0].available


@pytest.mark.asyncio
async def test_single_weak_business_match_is_one_match_not_auto_resolved() -> None:
    tradeflow = _tradeflow()
    tradeflow.products["BUS-1"] = {"BP-BOOM-500": tradeflow.products["BUS-1"]["BP-BOOM-500"]}

    resolution = await _resolver(tradeflow=tradeflow).resolve(
        "BUS-1",
        ProductQuery(original_text="Boom"),
    )

    assert resolution.status == ProductResolutionStatus.ONE_MATCH
    assert len(resolution.candidates) == 1
    assert resolution.selected is None


@pytest.mark.asyncio
async def test_hidden_business_product_is_never_returned() -> None:
    resolution = await _resolver().resolve(
        "BUS-1",
        ProductQuery(
            original_text="White Sugar 1kg",
            product_family="Sugar",
            size_value=Decimal("1"),
            size_unit="kg",
        ),
    )

    assert resolution.status == ProductResolutionStatus.NO_MATCH
    assert not resolution.candidates


@pytest.mark.asyncio
async def test_numbered_selection_resolves_candidate_with_business_facts() -> None:
    resolver = _resolver()
    initial = await resolver.resolve(
        "BUS-1",
        ProductQuery(original_text="Boom", brand="Boom"),
    )

    selected = resolver.resolve_selection(initial, 2)

    assert selected.status == ProductResolutionStatus.RESOLVED
    assert selected.selected is not None
    assert selected.selected.name == initial.candidates[1].name
    assert selected.selected.currency == "ZMW"


@pytest.mark.asyncio
async def test_size_text_selects_one_clarification_candidate() -> None:
    resolver = _resolver()
    initial = await resolver.resolve(
        "BUS-1",
        ProductQuery(original_text="Boom", brand="Boom"),
    )

    selected = resolver.resolve_selection(initial, "500g")

    assert selected.selected is not None
    assert selected.selected.business_product_id == "BP-BOOM-500"


@pytest.mark.asyncio
async def test_yes_can_confirm_single_candidate_only() -> None:
    tradeflow = _tradeflow()
    tradeflow.products["BUS-1"] = {"BP-BOOM-500": tradeflow.products["BUS-1"]["BP-BOOM-500"]}
    resolver = _resolver(tradeflow=tradeflow)
    initial = await resolver.resolve(
        "BUS-1",
        ProductQuery(original_text="Boom"),
    )

    selected = resolver.resolve_selection(initial, "yes")

    assert selected.selected is not None
    assert selected.selected.business_product_id == "BP-BOOM-500"


@pytest.mark.asyncio
async def test_yes_rejects_multi_candidate_clarification() -> None:
    resolver = _resolver()
    initial = await resolver.resolve(
        "BUS-1",
        ProductQuery(original_text="Boom", brand="Boom"),
    )

    with pytest.raises(ProductSelectionError, match="ambiguous"):
        resolver.resolve_selection(initial, "yes")


@pytest.mark.asyncio
async def test_out_of_range_selection_is_rejected() -> None:
    resolver = _resolver()
    initial = await resolver.resolve(
        "BUS-1",
        ProductQuery(original_text="Boom", brand="Boom"),
    )

    with pytest.raises(ProductSelectionError, match="outside"):
        resolver.resolve_selection(initial, 99)


def test_product_query_from_entities_parses_size_and_category() -> None:
    query = product_query_from_entities(
        EntitySet(
            query="Boom 1 kg",
            brand="Boom",
            product_family="Washing Powder",
            extras={"category": "Laundry"},
        )
    )

    assert query.size_value == Decimal("1")
    assert query.size_unit == "kg"
    assert query.category == "Laundry"


def test_product_query_from_entities_accepts_structured_size_extras() -> None:
    query = product_query_from_entities(
        EntitySet(
            query="Boom refill",
            extras={"size_value": "500", "size_unit": "G"},
        )
    )

    assert query.size_value == Decimal("500")
    assert query.size_unit == "g"


def test_resolver_configuration_rejects_invalid_threshold_order() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        ProductResolverConfig(
            suggestion_threshold=0.95,
            exact_match_threshold=0.90,
        )

@pytest.mark.asyncio
async def test_ncpc_miss_can_surface_pending_tradeflow_product_provisionally() -> None:
    tradeflow = InMemoryTradeFlow()
    tradeflow.products["BUS-1"] = {
        "BP-LOCAL-TOMATO": BusinessProduct(
            business_product_id="BP-LOCAL-TOMATO",
            ncpc_product_id=None,
            ncpc_variant_id=None,
            name="Tomato Sauce Local 500ml",
            selling_price=Decimal("28"),
            currency="ZMW",
            available_quantity=6,
            barcode="LOCAL-500",
            identity_status="awaiting_ncpc_review",
            shop_id="shop-main",
        )
    }
    resolver = ProductResolver(ncpc=InMemoryNCPC(()), tradeflow=tradeflow)

    resolution = await resolver.resolve("BUS-1", ProductQuery(original_text="Tomato Sauce Local"))

    assert resolution.status == ProductResolutionStatus.ONE_MATCH
    candidate = resolution.candidates[0]
    assert candidate.business_product_id == "BP-LOCAL-TOMATO"
    assert candidate.ncpc_product_id is None
    assert candidate.ncpc_variant_id is None
    assert candidate.identity_status == "awaiting_ncpc_review"
    assert candidate.trusted_identity is False
    assert candidate.catalogue_version == "tradeflow-provisional"
    assert candidate.shop_id == "shop-main"

    selected = resolver.resolve_selection(resolution, 1).selected
    assert selected is not None
    assert selected.ncpc_product_id is None
    assert selected.trusted_identity is False
    assert selected.identity_status == "awaiting_ncpc_review"
    assert selected.shop_id == "shop-main"


@pytest.mark.asyncio
@pytest.mark.parametrize("identity_status", ("local_only", "rejected", "needs_link", "link_error"))
async def test_untrusted_unsubmitted_or_rejected_tradeflow_product_is_not_ntheemba_visible(
    identity_status: str,
) -> None:
    tradeflow = InMemoryTradeFlow()
    tradeflow.products["BUS-1"] = {
        "BP-LOCAL": BusinessProduct(
            business_product_id="BP-LOCAL",
            ncpc_product_id=None,
            name="Local Test Product",
            selling_price=Decimal("10"),
            currency="ZMW",
            available_quantity=3,
            identity_status=identity_status,
        )
    }
    resolver = ProductResolver(ncpc=InMemoryNCPC(()), tradeflow=tradeflow)

    resolution = await resolver.resolve("BUS-1", ProductQuery(original_text="Local Test"))

    assert resolution.status == ProductResolutionStatus.NO_MATCH
    assert resolution.outcome == ProductResolutionOutcome.NCPC_NO_MATCH


@pytest.mark.asyncio
async def test_local_fallback_is_scoped_to_the_resolved_business_only() -> None:
    tradeflow = InMemoryTradeFlow()
    tradeflow.products["BUS-A"] = {
        "A-1": BusinessProduct(
            business_product_id="A-1",
            ncpc_product_id=None,
            name="House Brand Sugar",
            selling_price=Decimal("31"),
            currency="ZMW",
            available_quantity=4,
            identity_status="awaiting_ncpc_review",
        )
    }
    tradeflow.products["BUS-B"] = {
        "B-1": BusinessProduct(
            business_product_id="B-1",
            ncpc_product_id=None,
            name="House Brand Sugar",
            selling_price=Decimal("99"),
            currency="ZMW",
            available_quantity=10,
            identity_status="awaiting_ncpc_review",
        )
    }
    resolver = ProductResolver(ncpc=InMemoryNCPC(()), tradeflow=tradeflow)

    resolution = await resolver.resolve("BUS-A", ProductQuery(original_text="House Brand Sugar"))

    assert tuple(item.business_product_id for item in resolution.candidates) == ("A-1",)
    assert resolution.candidates[0].selling_price == Decimal("31")
    assert all(
        call[1][0] == "BUS-A"
        for call in tradeflow.calls
        if call[0] == "search_business_products"
    )


@pytest.mark.asyncio
async def test_barcode_ncpc_miss_can_use_same_business_pending_review_fallback() -> None:
    tradeflow = InMemoryTradeFlow()
    tradeflow.products["BUS-1"] = {
        "BP-PENDING": BusinessProduct(
            business_product_id="BP-PENDING",
            ncpc_product_id=None,
            name="Pending Barcode Product",
            selling_price=Decimal("12"),
            currency="ZMW",
            available_quantity=2,
            barcode="9990001112223",
            identity_status="awaiting_ncpc_review",
        )
    }
    resolver = ProductResolver(ncpc=InMemoryNCPC(()), tradeflow=tradeflow)

    resolution = await resolver.resolve(
        "BUS-1",
        ProductQuery(original_text="", barcode="9990001112223"),
    )

    assert resolution.status == ProductResolutionStatus.ONE_MATCH
    assert resolution.candidates[0].business_product_id == "BP-PENDING"
    assert resolution.candidates[0].trusted_identity is False
