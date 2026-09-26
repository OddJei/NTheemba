"""Port for the NTheemba Central Product Catalogue."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from ntheemba.domain.product_resolution import ProductQuery


@dataclass(frozen=True, slots=True)
class CanonicalProduct:
    """Business-independent product identity returned by NCPC."""

    product_id: str
    canonical_name: str
    variant_id: str | None = None
    brand: str | None = None
    product_family: str | None = None
    variant: str | None = None
    size_value: Decimal | None = None
    size_unit: str | None = None
    barcode: str | None = None
    category: str | None = None
    image_url: str | None = None
    aliases: tuple[str, ...] = ()
    catalogue_version: str = "unversioned"

    def __post_init__(self) -> None:
        if not self.product_id.strip():
            raise ValueError("product_id must not be empty")
        if self.variant_id is None:
            object.__setattr__(self, "variant_id", self.product_id)
        elif not self.variant_id.strip():
            raise ValueError("variant_id must not be empty")
        if not self.canonical_name.strip():
            raise ValueError("canonical_name must not be empty")
        if not self.catalogue_version.strip():
            raise ValueError("catalogue_version must not be empty")
        if (self.size_value is None) != (self.size_unit is None):
            raise ValueError("size_value and size_unit must be supplied together")
        if self.size_value is not None and self.size_value <= 0:
            raise ValueError("size_value must be greater than zero")
        if self.size_unit is not None:
            object.__setattr__(self, "size_unit", self.size_unit.strip().lower())


class NCPCPort(Protocol):
    """Find canonical product identity without business price or stock."""

    async def search_products(
        self,
        query: ProductQuery,
        *,
        limit: int = 20,
    ) -> tuple[CanonicalProduct, ...]:
        """Search canonical products using natural-language clues."""

    async def get_product(self, product_id: str) -> CanonicalProduct | None:
        """Retrieve one canonical product."""

    async def resolve_barcode(self, barcode: str) -> CanonicalProduct | None:
        """Resolve one exact product barcode."""
