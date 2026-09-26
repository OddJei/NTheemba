"""In-memory NCPC catalogue for deterministic tests."""

from __future__ import annotations

import re

from ntheemba.domain.product_resolution import ProductQuery
from ntheemba.ports.ncpc import CanonicalProduct


def _tokens(value: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", value.lower()))


class InMemoryNCPC:
    """Simple canonical catalogue supporting text and barcode lookup."""

    def __init__(self, products: tuple[CanonicalProduct, ...] = ()) -> None:
        self.products = {product.product_id: product for product in products}
        self.calls: list[tuple[str, object]] = []

    async def search_products(
        self,
        query: ProductQuery,
        *,
        limit: int = 20,
    ) -> tuple[CanonicalProduct, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        self.calls.append(("search_products", query))
        if query.barcode:
            product = await self.resolve_barcode(query.barcode)
            return (product,) if product is not None else ()

        query_tokens = _tokens(
            " ".join(
                value
                for value in (
                    query.original_text,
                    query.brand or "",
                    query.product_family or "",
                    query.variant or "",
                    query.category or "",
                )
                if value
            )
        )
        scored: list[tuple[int, CanonicalProduct]] = []
        for product in self.products.values():
            searchable = " ".join(
                value
                for value in (
                    product.canonical_name,
                    product.brand or "",
                    product.product_family or "",
                    product.variant or "",
                    product.category or "",
                    *product.aliases,
                )
                if value
            )
            score = len(query_tokens & _tokens(searchable))
            if not query_tokens or score:
                scored.append((score, product))
        scored.sort(key=lambda item: (-item[0], item[1].canonical_name.lower()))
        return tuple(product for _, product in scored[:limit])

    async def get_product(self, product_id: str) -> CanonicalProduct | None:
        self.calls.append(("get_product", product_id))
        return self.products.get(product_id)

    async def resolve_barcode(self, barcode: str) -> CanonicalProduct | None:
        self.calls.append(("resolve_barcode", barcode))
        normalized = barcode.strip()
        return next(
            (product for product in self.products.values() if product.barcode == normalized),
            None,
        )
