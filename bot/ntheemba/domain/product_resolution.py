"""Product identity models shared by NCPC and TradeFlow resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Final

from ntheemba.domain.enums import ProductResolutionOutcome, ProductResolutionStatus, RelativeSize

_MASS_FACTORS: Final[dict[str, Decimal]] = {
    "mg": Decimal("0.001"),
    "g": Decimal("1"),
    "kg": Decimal("1000"),
}
_VOLUME_FACTORS: Final[dict[str, Decimal]] = {
    "ml": Decimal("1"),
    "l": Decimal("1000"),
}


@dataclass(frozen=True, slots=True)
class ProductQuery:
    original_text: str
    brand: str | None = None
    product_family: str | None = None
    variant: str | None = None
    size_value: Decimal | None = None
    size_unit: str | None = None
    relative_size: RelativeSize | None = None
    barcode: str | None = None
    category: str | None = None

    def __post_init__(self) -> None:
        text = self.original_text.strip()
        if not text and not self.barcode:
            raise ValueError("a product query requires text or a barcode")
        if (self.size_value is None) != (self.size_unit is None):
            raise ValueError("size_value and size_unit must be supplied together")
        if self.size_value is not None and self.size_value <= 0:
            raise ValueError("size_value must be greater than zero")
        object.__setattr__(self, "original_text", text)
        if self.size_unit is not None:
            object.__setattr__(self, "size_unit", self.size_unit.strip().lower())


@dataclass(frozen=True, slots=True)
class ProductCandidate:
    ncpc_product_id: str | None
    name: str
    ncpc_variant_id: str | None = None
    brand: str | None = None
    variant: str | None = None
    size_value: Decimal | None = None
    size_unit: str | None = None
    barcode: str | None = None
    category: str | None = None
    business_product_id: str | None = None
    selling_price: Decimal | None = None
    currency: str | None = None
    available: bool | None = None
    public_visible: bool | None = None
    score: float = 0.0
    catalogue_version: str = "unversioned"
    candidate_order: int = 0
    shop_id: str = ""
    identity_status: str = "linked"
    trusted_identity: bool = True

    def __post_init__(self) -> None:
        if self.ncpc_product_id is not None:
            product_id = self.ncpc_product_id.strip()
            object.__setattr__(self, "ncpc_product_id", product_id or None)
        if self.ncpc_variant_id is None and self.ncpc_product_id is not None:
            object.__setattr__(self, "ncpc_variant_id", self.ncpc_product_id)
        elif self.ncpc_variant_id is not None:
            variant_id = self.ncpc_variant_id.strip()
            object.__setattr__(self, "ncpc_variant_id", variant_id or None)
        if self.trusted_identity and (not self.ncpc_product_id or not self.ncpc_variant_id):
            raise ValueError("trusted candidates require NCPC product and variant IDs")
        if not self.name.strip():
            raise ValueError("candidate name must not be empty")
        if (self.size_value is None) != (self.size_unit is None):
            raise ValueError("size_value and size_unit must be supplied together")
        if self.size_value is not None and self.size_value <= 0:
            raise ValueError("size_value must be greater than zero")
        if self.selling_price is not None and self.selling_price < 0:
            raise ValueError("selling_price must not be negative")
        if not 0 <= self.score <= 1:
            raise ValueError("score must be between zero and one")
        if self.candidate_order < 0:
            raise ValueError("candidate_order must not be negative")
        if not self.catalogue_version.strip():
            raise ValueError("catalogue_version must not be empty")
        object.__setattr__(self, "identity_status", self.identity_status.strip().lower() or "local_only")
        if self.size_unit is not None:
            object.__setattr__(self, "size_unit", self.size_unit.strip().lower())
        if self.currency is not None:
            currency = self.currency.strip().upper()
            if len(currency) != 3:
                raise ValueError("currency must use a three-letter code")
            object.__setattr__(self, "currency", currency)

    def normalized_size(self) -> tuple[str, Decimal] | None:
        if self.size_value is None or self.size_unit is None:
            return None
        if self.size_unit in _MASS_FACTORS:
            return ("mass_g", self.size_value * _MASS_FACTORS[self.size_unit])
        if self.size_unit in _VOLUME_FACTORS:
            return ("volume_ml", self.size_value * _VOLUME_FACTORS[self.size_unit])
        return None


@dataclass(frozen=True, slots=True)
class ResolvedProduct:
    ncpc_product_id: str | None
    business_product_id: str
    name: str
    selling_price: Decimal
    currency: str
    available: bool
    size_value: Decimal | None = None
    size_unit: str | None = None
    barcode: str | None = None
    business_id: str = ""
    ncpc_variant_id: str | None = None
    shop_id: str = ""
    identity_status: str = "linked"
    trusted_identity: bool = True

    def __post_init__(self) -> None:
        if not self.business_product_id.strip():
            raise ValueError("business_product_id must not be empty")
        if self.ncpc_product_id is not None:
            product_id = self.ncpc_product_id.strip()
            object.__setattr__(self, "ncpc_product_id", product_id or None)
        if self.ncpc_variant_id is None and self.ncpc_product_id is not None:
            object.__setattr__(self, "ncpc_variant_id", self.ncpc_product_id)
        elif self.ncpc_variant_id is not None:
            variant_id = self.ncpc_variant_id.strip()
            object.__setattr__(self, "ncpc_variant_id", variant_id or None)
        if self.trusted_identity and (not self.ncpc_product_id or not self.ncpc_variant_id):
            raise ValueError("trusted resolved products require NCPC product and variant IDs")
        if not self.name.strip():
            raise ValueError("resolved product name must not be empty")
        if self.selling_price < 0:
            raise ValueError("selling_price must not be negative")
        currency = self.currency.strip().upper()
        if len(currency) != 3:
            raise ValueError("currency must use a three-letter code")
        object.__setattr__(self, "currency", currency)
        if (self.size_value is None) != (self.size_unit is None):
            raise ValueError("size_value and size_unit must be supplied together")
        if self.size_value is not None and self.size_value <= 0:
            raise ValueError("size_value must be greater than zero")
        if self.size_unit is not None:
            object.__setattr__(self, "size_unit", self.size_unit.strip().lower())
        object.__setattr__(self, "identity_status", self.identity_status.strip().lower() or "local_only")


@dataclass(frozen=True, slots=True)
class ProductResolution:
    query: ProductQuery
    status: ProductResolutionStatus = ProductResolutionStatus.NOT_STARTED
    candidates: tuple[ProductCandidate, ...] = field(default_factory=tuple)
    selected: ResolvedProduct | None = None
    confidence: float = 0.0
    clarification_options: tuple[str, ...] = field(default_factory=tuple)
    business_id: str = ""
    customer_id: str = ""
    conversation_id: str = ""
    catalogue_version: str = "unversioned"
    expires_at: datetime | None = None
    correlation_id: str = ""
    outcome: ProductResolutionOutcome | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between zero and one")
        if self.status == ProductResolutionStatus.RESOLVED and self.selected is None:
            raise ValueError("a resolved product resolution requires selected")
        if self.status != ProductResolutionStatus.RESOLVED and self.selected is not None:
            raise ValueError("selected is only valid when status is resolved")
        if (
            self.status
            in {
                ProductResolutionStatus.ONE_MATCH,
                ProductResolutionStatus.SUGGEST_CONFIRMATION,
            }
            and not self.candidates
        ):
            raise ValueError("single-candidate outcomes require candidates")
        if self.status == ProductResolutionStatus.ONE_MATCH and len(self.candidates) != 1:
            raise ValueError("one-match resolution requires exactly one candidate")
        if self.status == ProductResolutionStatus.SUGGEST_CONFIRMATION and not self.candidates:
            raise ValueError("suggestion requires at least one candidate")
        if self.status == ProductResolutionStatus.NEEDS_CLARIFICATION and len(self.candidates) < 2:
            raise ValueError("clarification requires at least two candidates")
        if self.clarification_options and len(self.clarification_options) != len(self.candidates):
            raise ValueError("clarification options must align with candidates")
        if self.catalogue_version and not self.catalogue_version.strip():
            raise ValueError("catalogue_version must not be blank")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        if self.status == ProductResolutionStatus.NO_MATCH and self.outcome not in {
            ProductResolutionOutcome.NCPC_NO_MATCH,
            ProductResolutionOutcome.SHOP_NO_MATCH,
        }:
            raise ValueError("no-match resolutions require a no-match outcome")

    @classmethod
    def no_match(
        cls,
        query: ProductQuery,
        *,
        outcome: ProductResolutionOutcome = ProductResolutionOutcome.NCPC_NO_MATCH,
    ) -> ProductResolution:
        if outcome not in {
            ProductResolutionOutcome.NCPC_NO_MATCH,
            ProductResolutionOutcome.SHOP_NO_MATCH,
        }:
            raise ValueError("no-match outcome must be NCPC_NO_MATCH or SHOP_NO_MATCH")
        return cls(query=query, status=ProductResolutionStatus.NO_MATCH, outcome=outcome)

    @classmethod
    def one_match(
        cls,
        query: ProductQuery,
        candidate: ProductCandidate,
        *,
        confidence: float,
    ) -> ProductResolution:
        return cls(
            query=query,
            status=ProductResolutionStatus.ONE_MATCH,
            candidates=(candidate,),
            confidence=confidence,
        )

    @classmethod
    def suggestion(
        cls,
        query: ProductQuery,
        candidate: ProductCandidate,
        *,
        confidence: float,
        candidates: tuple[ProductCandidate, ...] = (),
    ) -> ProductResolution:
        ordered = (
            candidate,
            *(item for item in candidates if item != candidate),
        )
        return cls(
            query=query,
            status=ProductResolutionStatus.SUGGEST_CONFIRMATION,
            candidates=ordered,
            confidence=confidence,
        )

    @classmethod
    def needs_clarification(
        cls,
        query: ProductQuery,
        candidates: tuple[ProductCandidate, ...],
        *,
        confidence: float,
        options: tuple[str, ...],
    ) -> ProductResolution:
        return cls(
            query=query,
            status=ProductResolutionStatus.NEEDS_CLARIFICATION,
            candidates=candidates,
            confidence=confidence,
            clarification_options=options,
        )

    def scoped(
        self,
        *,
        business_id: str,
        customer_id: str,
        conversation_id: str,
        expires_at: datetime,
        correlation_id: str,
    ) -> ProductResolution:
        """Return this pending candidate set scoped to one tenant session."""

        if not business_id.strip() or not customer_id.strip() or not conversation_id.strip():
            raise ValueError("pending candidate scope IDs must not be empty")
        if not correlation_id.strip():
            raise ValueError("correlation_id must not be empty")
        catalogue_version = self.catalogue_version
        if self.candidates:
            catalogue_version = self.candidates[0].catalogue_version
        return ProductResolution(
            query=self.query,
            status=self.status,
            candidates=self.candidates,
            selected=self.selected,
            confidence=self.confidence,
            clarification_options=self.clarification_options,
            business_id=business_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            catalogue_version=catalogue_version,
            expires_at=expires_at,
            correlation_id=correlation_id,
            outcome=self.outcome,
        )

    @classmethod
    def resolved(
        cls,
        query: ProductQuery,
        selected: ResolvedProduct,
        *,
        confidence: float,
        candidates: tuple[ProductCandidate, ...] = (),
    ) -> ProductResolution:
        return cls(
            query=query,
            status=ProductResolutionStatus.RESOLVED,
            candidates=candidates,
            selected=selected,
            confidence=confidence,
        )
