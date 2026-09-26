"""NCPC-backed canonical product resolution filtered through TradeFlow."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from ntheemba.domain.enums import (
    ProductResolutionOutcome,
    ProductResolutionStatus,
    RelativeSize,
)
from ntheemba.domain.intents import EntitySet
from ntheemba.domain.product_resolution import (
    ProductCandidate,
    ProductQuery,
    ProductResolution,
    ResolvedProduct,
)
from ntheemba.ports.ncpc import CanonicalProduct, NCPCPort
from ntheemba.ports.tradeflow import BusinessProduct, TradeFlowPort

_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"[a-z0-9]+")
_SIZE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(mg|kg|g|ml|l)\b",
    re.IGNORECASE,
)
_SELECTION_NUMBER_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\s*(\d+)\s*[.)]?\s*$")
_CONFIRMATION_WORDS: Final[frozenset[str]] = frozenset(
    {"yes", "yeah", "yep", "correct", "confirm", "that one", "this one"}
)
_QUERY_STOP_WORDS: Final[frozenset[str]] = frozenset(
    {
        "a",
        "an",
        "buy",
        "can",
        "could",
        "find",
        "for",
        "get",
        "i",
        "item",
        "large",
        "largest",
        "medium",
        "need",
        "order",
        "please",
        "product",
        "small",
        "smallest",
        "some",
        "the",
        "want",
        "would",
    }
)


class ProductResolutionError(ValueError):
    """Base error for invalid product resolution operations."""


class ProductResolutionDependencyError(ProductResolutionError):
    """Raised when NCPC or TradeFlow cannot be safely used for resolution."""

    def __init__(
        self,
        *,
        outcome: ProductResolutionOutcome,
        dependency: str,
        operation: str,
        retryable: bool,
    ) -> None:
        super().__init__(outcome.value)
        self.outcome = outcome
        self.dependency = dependency
        self.operation = operation
        self.retryable = retryable


class ProductSelectionError(ProductResolutionError):
    """Raised when a customer selection cannot identify one candidate."""


class ProductNoneOfTheseError(ProductSelectionError):
    """Raised when the customer rejects the presented candidate set."""


@dataclass(frozen=True, slots=True)
class ProductResolverConfig:
    """Ranking thresholds and bounded result sizes."""

    ncpc_search_limit: int = 30
    max_candidates: int = 5
    exact_match_threshold: float = 0.90
    suggestion_threshold: float = 0.70
    dominance_gap: float = 0.12

    def __post_init__(self) -> None:
        if self.ncpc_search_limit <= 0:
            raise ValueError("ncpc_search_limit must be greater than zero")
        if self.max_candidates < 2:
            raise ValueError("max_candidates must be at least two")
        for field_name, value in {
            "exact_match_threshold": self.exact_match_threshold,
            "suggestion_threshold": self.suggestion_threshold,
            "dominance_gap": self.dominance_gap,
        }.items():
            if not 0 <= value <= 1:
                raise ValueError(f"{field_name} must be between zero and one")
        if self.suggestion_threshold > self.exact_match_threshold:
            raise ValueError("suggestion_threshold must not exceed exact_match_threshold")


@dataclass(frozen=True, slots=True)
class _ScoredProduct:
    canonical: CanonicalProduct
    business: BusinessProduct
    candidate: ProductCandidate
    score: float
    exact_name_match: bool
    exact_size_match: bool


class ProductResolver:
    """Resolve customer product language into one business product."""

    def __init__(
        self,
        *,
        ncpc: NCPCPort,
        tradeflow: TradeFlowPort,
        config: ProductResolverConfig | None = None,
    ) -> None:
        self.ncpc = ncpc
        self.tradeflow = tradeflow
        self.config = config or ProductResolverConfig()

    async def resolve(
        self,
        business_id: str,
        query: ProductQuery,
    ) -> ProductResolution:
        """Resolve a query through NCPC and the business TradeFlow catalogue."""

        normalized_business_id = business_id.strip()
        if not normalized_business_id:
            raise ProductResolutionError("business_id must not be empty")

        if query.barcode:
            resolution = await self._resolve_barcode(normalized_business_id, query)
            return _with_business_scope(resolution, normalized_business_id)

        canonical_products = await _read_dependency(
            self.ncpc.search_products(
                query,
                limit=self.config.ncpc_search_limit,
            ),
            dependency="ncpc",
            operation="search_products",
            timeout_outcome=ProductResolutionOutcome.NCPC_TIMEOUT,
        )
        if not canonical_products:
            resolution = await self._resolve_local_fallback(normalized_business_id, query)
            return _with_business_scope(resolution, normalized_business_id)

        resolution = await self._resolve_canonical_candidates(
            normalized_business_id,
            query,
            canonical_products,
        )
        return _with_business_scope(resolution, normalized_business_id)

    async def resolve_from_entities(
        self,
        business_id: str,
        entities: EntitySet,
    ) -> ProductResolution:
        """Build a typed query from interpreted entities and resolve it."""

        return await self.resolve(
            business_id,
            product_query_from_entities(entities),
        )

    def resolve_selection(
        self,
        resolution: ProductResolution,
        selection: str | int,
    ) -> ProductResolution:
        """Resolve a numbered, named, sized, or affirmative candidate choice."""

        candidates = resolution.candidates
        if not candidates:
            raise ProductSelectionError("the resolution has no selectable candidates")

        selected = self._select_candidate(
            candidates,
            resolution.clarification_options,
            selection,
            allow_primary_confirmation=(
                resolution.status == ProductResolutionStatus.SUGGEST_CONFIRMATION
            ),
        )
        return ProductResolution.resolved(
            resolution.query,
            self._resolved_product(resolution.business_id, selected),
            confidence=1.0,
            candidates=candidates,
        )

    async def _resolve_barcode(
        self,
        business_id: str,
        query: ProductQuery,
    ) -> ProductResolution:
        canonical = await _read_dependency(
            self.ncpc.resolve_barcode(query.barcode or ""),
            dependency="ncpc",
            operation="resolve_barcode",
            timeout_outcome=ProductResolutionOutcome.NCPC_TIMEOUT,
        )
        if canonical is None:
            return await self._resolve_local_fallback(
                business_id,
                query,
                no_match_outcome=ProductResolutionOutcome.NCPC_NO_MATCH,
            )

        business_products = await _read_dependency(
            self.tradeflow.filter_business_products(
                business_id,
                (canonical.variant_id or canonical.product_id,),
            ),
            dependency="tradeflow",
            operation="filter_business_products",
            timeout_outcome=ProductResolutionOutcome.TRADEFLOW_TIMEOUT,
        )
        scored = self._merge_and_score(query, (canonical,), business_products)
        if not scored:
            return await self._resolve_local_fallback(
                business_id,
                query,
                no_match_outcome=ProductResolutionOutcome.SHOP_NO_MATCH,
            )
        candidates = _ordered_candidates(
            tuple(item.candidate for item in scored[: self.config.max_candidates])
        )
        if len(candidates) == 1:
            return ProductResolution.one_match(
                query,
                candidates[0],
                confidence=1.0,
            )
        return ProductResolution.needs_clarification(
            query,
            candidates,
            confidence=1.0,
            options=self._clarification_options(candidates),
        )

    async def _resolve_local_fallback(
        self,
        business_id: str,
        query: ProductQuery,
        *,
        no_match_outcome: ProductResolutionOutcome = ProductResolutionOutcome.NCPC_NO_MATCH,
    ) -> ProductResolution:
        """Search only the active tenant when NCPC has no canonical match.

        Only NCPC-linked or submitted/pending-review products may surface.  Local-only,
        rejected, stale, or error states remain fully operational in TradeFlow but are not
        visible through Ntheemba.  Pending products stay explicitly provisional and never
        receive fabricated canonical identifiers.
        """

        products = await _read_dependency(
            self.tradeflow.search_business_products(
                business_id,
                query.barcode or query.original_text,
                limit=self.config.max_candidates,
            ),
            dependency="tradeflow",
            operation="search_business_products",
            timeout_outcome=ProductResolutionOutcome.TRADEFLOW_TIMEOUT,
        )
        allowed = tuple(
            product
            for product in products
            if product.public_visible
            and product.identity_status in {"linked", "awaiting_ncpc_review"}
        )
        if not allowed:
            return ProductResolution.no_match(
                query,
                outcome=no_match_outcome,
            )

        candidates = tuple(
            ProductCandidate(
                ncpc_product_id=product.ncpc_product_id,
                ncpc_variant_id=product.ncpc_variant_id,
                name=product.name,
                business_product_id=product.business_product_id,
                selling_price=product.selling_price,
                currency=product.currency,
                available=product.available,
                public_visible=product.public_visible,
                barcode=product.barcode,
                score=0.78 if product.trusted_identity else 0.70,
                catalogue_version=(
                    "tradeflow-linked-fallback"
                    if product.trusted_identity
                    else "tradeflow-provisional"
                ),
                shop_id=product.shop_id,
                identity_status=product.identity_status,
                trusted_identity=product.trusted_identity,
            )
            for product in sorted(
                allowed,
                key=lambda item: (
                    not item.trusted_identity,
                    not item.available,
                    item.name.casefold(),
                    item.business_product_id,
                ),
            )
        )
        ordered = _ordered_candidates(candidates)
        if len(ordered) == 1:
            return ProductResolution.one_match(
                query,
                ordered[0],
                confidence=ordered[0].score,
            )
        return ProductResolution.needs_clarification(
            query,
            ordered,
            confidence=max(item.score for item in ordered),
            options=self._clarification_options(ordered),
        )

    async def _resolve_canonical_candidates(
        self,
        business_id: str,
        query: ProductQuery,
        canonical_products: Sequence[CanonicalProduct],
    ) -> ProductResolution:
        unique_canonical = _deduplicate_canonical(canonical_products)
        ids = tuple(product.variant_id or product.product_id for product in unique_canonical)
        business_products = await _read_dependency(
            self.tradeflow.filter_business_products(
                business_id,
                ids,
            ),
            dependency="tradeflow",
            operation="filter_business_products",
            timeout_outcome=ProductResolutionOutcome.TRADEFLOW_TIMEOUT,
        )
        scored = self._merge_and_score(query, unique_canonical, business_products)
        if not scored:
            return await self._resolve_local_fallback(
                business_id,
                query,
                no_match_outcome=ProductResolutionOutcome.SHOP_NO_MATCH,
            )

        scored = self._apply_relative_size_preference(query, scored)
        scored = tuple(
            sorted(
                scored,
                key=_scored_sort_key,
            )
        )
        limited = scored[: self.config.max_candidates]
        candidates = _ordered_candidates(tuple(item.candidate for item in limited))
        top = limited[0]

        if len(limited) == 1:
            return ProductResolution.one_match(
                query,
                candidates[0],
                confidence=top.score,
            )

        confidence = max(item.score for item in limited)
        return ProductResolution.needs_clarification(
            query,
            candidates,
            confidence=confidence,
            options=self._clarification_options(candidates),
        )

    def _merge_and_score(
        self,
        query: ProductQuery,
        canonical_products: Sequence[CanonicalProduct],
        business_products: Sequence[BusinessProduct],
    ) -> tuple[_ScoredProduct, ...]:
        canonical_by_id = {
            product.variant_id or product.product_id: product for product in canonical_products
        }
        merged: list[_ScoredProduct] = []
        for business in business_products:
            if not business.public_visible:
                continue
            canonical = canonical_by_id.get(business.ncpc_variant_id or business.ncpc_product_id)
            if canonical is None:
                continue
            if _structured_identity_conflicts(query, canonical):
                continue
            score, exact_name, exact_size = _score_product(
                query,
                canonical,
                business,
            )
            candidate = ProductCandidate(
                ncpc_product_id=canonical.product_id,
                ncpc_variant_id=canonical.variant_id or canonical.product_id,
                name=business.name,
                brand=canonical.brand,
                variant=canonical.variant,
                size_value=canonical.size_value,
                size_unit=canonical.size_unit,
                barcode=canonical.barcode,
                category=canonical.category,
                business_product_id=business.business_product_id,
                selling_price=business.selling_price,
                currency=business.currency,
                available=business.available,
                public_visible=business.public_visible,
                score=score,
                catalogue_version=canonical.catalogue_version,
                shop_id=business.shop_id,
                identity_status=business.identity_status,
                trusted_identity=True,
            )
            merged.append(
                _ScoredProduct(
                    canonical=canonical,
                    business=business,
                    candidate=candidate,
                    score=score,
                    exact_name_match=exact_name,
                    exact_size_match=exact_size,
                )
            )
        return tuple(merged)

    def _apply_relative_size_preference(
        self,
        query: ProductQuery,
        scored: Sequence[_ScoredProduct],
    ) -> tuple[_ScoredProduct, ...]:
        target = self._relative_target(query, scored)
        if target is None:
            return tuple(scored)

        updated: list[_ScoredProduct] = []
        for item in scored:
            bonus = 0.28 if item is target else 0.0
            score = min(1.0, item.score + bonus)
            updated.append(
                _ScoredProduct(
                    canonical=item.canonical,
                    business=item.business,
                    candidate=ProductCandidate(
                        ncpc_product_id=item.candidate.ncpc_product_id,
                        ncpc_variant_id=item.candidate.ncpc_variant_id,
                        name=item.candidate.name,
                        brand=item.candidate.brand,
                        variant=item.candidate.variant,
                        size_value=item.candidate.size_value,
                        size_unit=item.candidate.size_unit,
                        barcode=item.candidate.barcode,
                        category=item.candidate.category,
                        business_product_id=item.candidate.business_product_id,
                        selling_price=item.candidate.selling_price,
                        currency=item.candidate.currency,
                        available=item.candidate.available,
                        public_visible=item.candidate.public_visible,
                        score=score,
                        catalogue_version=item.candidate.catalogue_version,
                        candidate_order=item.candidate.candidate_order,
                        shop_id=item.candidate.shop_id,
                        identity_status=item.candidate.identity_status,
                        trusted_identity=item.candidate.trusted_identity,
                    ),
                    score=score,
                    exact_name_match=item.exact_name_match,
                    exact_size_match=item.exact_size_match,
                )
            )
        return tuple(updated)

    @staticmethod
    def _relative_target(
        query: ProductQuery,
        scored: Sequence[_ScoredProduct],
    ) -> _ScoredProduct | None:
        if query.relative_size is None:
            return None

        groups: dict[str, list[tuple[Decimal, _ScoredProduct]]] = {}
        for item in scored:
            normalized = item.candidate.normalized_size()
            if normalized is None:
                continue
            dimension, value = normalized
            groups.setdefault(dimension, []).append((value, item))

        if not groups:
            return None

        largest_group = max(
            groups.values(),
            key=lambda values: (len(values), max(value for value, _ in values)),
        )
        if len(largest_group) < 2:
            return largest_group[0][1]

        ordered = sorted(
            largest_group,
            key=lambda pair: (pair[0], pair[1].business.name.casefold()),
        )
        index_map = {
            RelativeSize.SMALLEST: 0,
            RelativeSize.SMALL: round((len(ordered) - 1) * 0.25),
            RelativeSize.MEDIUM: round((len(ordered) - 1) * 0.50),
            RelativeSize.LARGE: round((len(ordered) - 1) * 0.75),
            RelativeSize.LARGEST: len(ordered) - 1,
        }
        return ordered[index_map[query.relative_size]][1]

    @staticmethod
    def _select_candidate(
        candidates: Sequence[ProductCandidate],
        options: Sequence[str],
        selection: str | int,
        *,
        allow_primary_confirmation: bool = False,
    ) -> ProductCandidate:
        if isinstance(selection, int):
            index = selection - 1
            if 0 <= index < len(candidates):
                return candidates[index]
            raise ProductSelectionError("selection number is outside the candidate list")

        cleaned = _normalize_text(selection)
        if not cleaned:
            raise ProductSelectionError("selection must not be empty")

        number_match = _SELECTION_NUMBER_PATTERN.fullmatch(selection)
        if number_match:
            index = int(number_match.group(1)) - 1
            if 0 <= index < len(candidates):
                return candidates[index]
            raise ProductSelectionError("selection number is outside the candidate list")

        if cleaned in _CONFIRMATION_WORDS:
            if len(candidates) == 1 or allow_primary_confirmation:
                return candidates[0]
            raise ProductSelectionError(
                "confirmation is ambiguous because several candidates remain"
            )

        if _is_none_of_these(cleaned):
            raise ProductNoneOfTheseError("customer rejected the pending candidates")

        matches: list[ProductCandidate] = []
        for index, candidate in enumerate(candidates):
            labels = {
                _normalize_text(candidate.name),
                _normalize_text(_candidate_label(candidate)),
            }
            if candidate.variant:
                labels.add(_normalize_text(candidate.variant))
            if candidate.barcode:
                labels.add(_normalize_text(candidate.barcode))
            if index < len(options):
                labels.add(_normalize_text(options[index]))
            if cleaned in labels or any(cleaned in label for label in labels):
                matches.append(candidate)

        unique = _deduplicate_candidates(matches)
        if len(unique) == 1:
            return unique[0]
        if not unique:
            raise ProductSelectionError("selection did not match any candidate")
        raise ProductSelectionError("selection matched more than one candidate")

    @staticmethod
    def _resolved_product(business_id: str, candidate: ProductCandidate) -> ResolvedProduct:
        if not business_id.strip():
            raise ProductSelectionError("resolution has no business scope")
        if not candidate.business_product_id:
            raise ProductSelectionError("candidate has no business product identity")
        if candidate.selling_price is None or candidate.currency is None:
            raise ProductSelectionError("candidate has no business price")
        if candidate.available is None:
            raise ProductSelectionError("candidate has no availability state")
        return ResolvedProduct(
            business_id=business_id,
            ncpc_product_id=candidate.ncpc_product_id,
            ncpc_variant_id=candidate.ncpc_variant_id,
            business_product_id=candidate.business_product_id,
            name=candidate.name,
            selling_price=candidate.selling_price,
            currency=candidate.currency,
            available=candidate.available,
            size_value=candidate.size_value,
            size_unit=candidate.size_unit,
            barcode=candidate.barcode,
            shop_id=candidate.shop_id,
            identity_status=candidate.identity_status,
            trusted_identity=candidate.trusted_identity,
        )

    @staticmethod
    def _clarification_options(
        candidates: Sequence[ProductCandidate],
    ) -> tuple[str, ...]:
        return tuple(_candidate_display_label(candidate) for candidate in candidates)


def product_query_from_entities(entities: EntitySet) -> ProductQuery:
    """Convert interpreted message entities into a typed product query."""

    raw = (entities.query or entities.raw_text).strip()
    size_value, size_unit = _size_from_entities(entities, raw)

    identity_parts = [
        value
        for value in (
            entities.brand,
            entities.product_family,
            entities.variant,
        )
        if value
    ]
    original_text = raw or " ".join(identity_parts).strip()
    if not original_text and not entities.barcode:
        raise ProductResolutionError(
            "product entities require query text, identity clues, or a barcode"
        )

    return ProductQuery(
        original_text=original_text,
        brand=entities.brand,
        product_family=entities.product_family,
        variant=entities.variant,
        size_value=size_value,
        size_unit=size_unit,
        relative_size=entities.relative_size,
        barcode=entities.barcode,
        category=_optional_text(entities.extras.get("category")),
    )


def _size_from_entities(
    entities: EntitySet,
    raw: str,
) -> tuple[Decimal | None, str | None]:
    extra_value = entities.extras.get("size_value")
    extra_unit = _optional_text(entities.extras.get("size_unit"))
    if extra_value is not None and extra_unit is not None:
        try:
            value = Decimal(str(extra_value).replace(",", "."))
        except InvalidOperation as error:
            raise ProductResolutionError("size_value is not a valid decimal") from error
        return value, extra_unit.lower()

    match = _SIZE_PATTERN.search(raw)
    if match is None:
        return None, None
    return Decimal(match.group(1).replace(",", ".")), match.group(2).lower()


def _scored_sort_key(
    item: _ScoredProduct,
) -> tuple[float, str, Decimal, bool, str]:
    normalized = item.candidate.normalized_size()
    if normalized is None:
        dimension = "zz"
        size = Decimal("Infinity")
    else:
        dimension, size = normalized
    return (
        -item.score,
        dimension,
        size,
        not item.business.available,
        item.business.name.casefold(),
    )


def _score_product(
    query: ProductQuery,
    canonical: CanonicalProduct,
    business: BusinessProduct,
) -> tuple[float, bool, bool]:
    query_text = _normalize_text(query.original_text)
    searchable_text = _normalize_text(
        " ".join(
            value
            for value in (
                canonical.canonical_name,
                business.name,
                canonical.brand or "",
                canonical.product_family or "",
                canonical.variant or "",
                canonical.category or "",
                *canonical.aliases,
            )
            if value
        )
    )

    query_tokens = {
        token
        for token in _tokens(query_text)
        if token not in _QUERY_STOP_WORDS and not token.isdigit()
    }
    product_tokens = _tokens(searchable_text)
    overlap = query_tokens & product_tokens

    score = 0.0
    if query_tokens:
        score += 0.45 * (len(overlap) / len(query_tokens))
    score += _field_match_score(query.brand, canonical.brand, 0.15)
    score += _field_match_score(
        query.product_family,
        canonical.product_family,
        0.15,
    )
    score += _field_match_score(query.variant, canonical.variant, 0.10)
    score += _field_match_score(query.category, canonical.category, 0.05)

    exact_size = _sizes_equal(
        query.size_value,
        query.size_unit,
        canonical.size_value,
        canonical.size_unit,
    )
    if query.size_value is not None:
        score += 0.25 if exact_size else -0.15

    canonical_name = _normalize_text(canonical.canonical_name)
    business_name = _normalize_text(business.name)
    exact_name = bool(query_text) and query_text in {
        canonical_name,
        business_name,
    }
    if exact_name:
        score += 0.20

    return min(1.0, max(0.0, score)), exact_name, exact_size


def _structured_identity_conflicts(
    query: ProductQuery,
    canonical: CanonicalProduct,
) -> bool:
    pairs = (
        (query.brand, canonical.brand),
        (query.product_family, canonical.product_family),
        (query.variant, canonical.variant),
        (query.category, canonical.category),
    )
    for query_value, canonical_value in pairs:
        if not query_value or not canonical_value:
            continue
        left = _normalize_text(query_value)
        right = _normalize_text(canonical_value)
        if left != right and left not in right and right not in left:
            return True
    return False


def _field_match_score(
    query_value: str | None,
    product_value: str | None,
    weight: float,
) -> float:
    if not query_value or not product_value:
        return 0.0
    query_normalized = _normalize_text(query_value)
    product_normalized = _normalize_text(product_value)
    if query_normalized == product_normalized:
        return weight
    if query_normalized in product_normalized or product_normalized in query_normalized:
        return weight * 0.70
    return 0.0


def _sizes_equal(
    left_value: Decimal | None,
    left_unit: str | None,
    right_value: Decimal | None,
    right_unit: str | None,
) -> bool:
    if left_value is None or left_unit is None or right_value is None or right_unit is None:
        return False
    left = ProductCandidate(
        ncpc_product_id="LEFT",
        ncpc_variant_id="LEFT",
        name="left",
        size_value=left_value,
        size_unit=left_unit,
    ).normalized_size()
    right = ProductCandidate(
        ncpc_product_id="RIGHT",
        ncpc_variant_id="RIGHT",
        name="right",
        size_value=right_value,
        size_unit=right_unit,
    ).normalized_size()
    if left is not None and right is not None:
        return left == right
    return left_value == right_value and left_unit.casefold() == right_unit.casefold()


def _has_identity_clue(query: ProductQuery) -> bool:
    if any((query.brand, query.product_family, query.variant, query.category)):
        return True
    cleaned_tokens = {
        token
        for token in _tokens(_SIZE_PATTERN.sub("", query.original_text))
        if token not in _QUERY_STOP_WORDS
    }
    return bool(cleaned_tokens)


def _candidate_label(candidate: ProductCandidate) -> str:
    name = " ".join(candidate.name.split())
    if candidate.size_value is None or candidate.size_unit is None:
        return name
    value = format(candidate.size_value.normalize(), "f")
    size = f"{value}{candidate.size_unit}"
    if _normalize_text(size) in _normalize_text(name):
        return name
    return f"{name} — {size}"


def _candidate_display_label(candidate: ProductCandidate) -> str:
    label = _candidate_label(candidate)
    details: list[str] = []
    if candidate.selling_price is not None and candidate.currency is not None:
        details.append(f"{candidate.currency} {candidate.selling_price:.2f}")
    if candidate.available is not None:
        details.append("available" if candidate.available else "currently unavailable")
    if not details:
        return label
    return f"{label} ({', '.join(details)})"


def _deduplicate_canonical(
    products: Sequence[CanonicalProduct],
) -> tuple[CanonicalProduct, ...]:
    seen: set[str] = set()
    result: list[CanonicalProduct] = []
    for product in products:
        if product.product_id in seen:
            continue
        seen.add(product.product_id)
        result.append(product)
    return tuple(result)


def _deduplicate_candidates(
    candidates: Sequence[ProductCandidate],
) -> tuple[ProductCandidate, ...]:
    seen: set[tuple[str, str | None]] = set()
    result: list[ProductCandidate] = []
    for candidate in candidates:
        key = (candidate.ncpc_product_id, candidate.business_product_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return tuple(result)


def _ordered_candidates(
    candidates: Sequence[ProductCandidate],
) -> tuple[ProductCandidate, ...]:
    ordered: list[ProductCandidate] = []
    for index, candidate in enumerate(candidates, start=1):
        ordered.append(
            ProductCandidate(
                ncpc_product_id=candidate.ncpc_product_id,
                ncpc_variant_id=candidate.ncpc_variant_id,
                name=candidate.name,
                brand=candidate.brand,
                variant=candidate.variant,
                size_value=candidate.size_value,
                size_unit=candidate.size_unit,
                barcode=candidate.barcode,
                category=candidate.category,
                business_product_id=candidate.business_product_id,
                selling_price=candidate.selling_price,
                currency=candidate.currency,
                available=candidate.available,
                public_visible=candidate.public_visible,
                score=candidate.score,
                catalogue_version=candidate.catalogue_version,
                candidate_order=index,
                shop_id=candidate.shop_id,
                identity_status=candidate.identity_status,
                trusted_identity=candidate.trusted_identity,
            )
        )
    return tuple(ordered)


def _with_business_scope(
    resolution: ProductResolution,
    business_id: str,
) -> ProductResolution:
    return ProductResolution(
        query=resolution.query,
        status=resolution.status,
        candidates=resolution.candidates,
        selected=resolution.selected,
        confidence=resolution.confidence,
        clarification_options=resolution.clarification_options,
        business_id=business_id,
        catalogue_version=resolution.catalogue_version,
        outcome=resolution.outcome,
    )


async def _read_dependency(
    awaitable: Awaitable[Any],
    *,
    dependency: str,
    operation: str,
    timeout_outcome: ProductResolutionOutcome,
) -> Any:
    try:
        return await awaitable
    except TimeoutError as error:
        raise ProductResolutionDependencyError(
            outcome=timeout_outcome,
            dependency=dependency,
            operation=operation,
            retryable=True,
        ) from error
    except PermissionError as error:
        raise ProductResolutionDependencyError(
            outcome=ProductResolutionOutcome.AUTH_FAILURE,
            dependency=dependency,
            operation=operation,
            retryable=False,
        ) from error
    except (TypeError, ValueError) as error:
        raise ProductResolutionDependencyError(
            outcome=ProductResolutionOutcome.MALFORMED_RESPONSE,
            dependency=dependency,
            operation=operation,
            retryable=False,
        ) from error


def _is_none_of_these(cleaned: str) -> bool:
    return cleaned in {
        "none",
        "none of these",
        "not these",
        "not any",
        "no",
        "wrong",
        "speak to person",
        "human",
        "agent",
    }


def _normalize_text(value: str) -> str:
    return " ".join(_TOKEN_PATTERN.findall(value.casefold()))


def _tokens(value: str) -> frozenset[str]:
    return frozenset(_TOKEN_PATTERN.findall(value.casefold()))


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
