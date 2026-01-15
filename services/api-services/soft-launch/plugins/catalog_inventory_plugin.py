"""
Catalog + Inventory plugin wrapper.
"""
from __future__ import annotations

from typing import Any, Dict

from contracts.python.soft_launch_client.client import AsyncServiceClient
from contracts.python.soft_launch_client.models import OperationSpec
from contracts.python.soft_launch_client.transports.httpx_async import HttpxAsyncTransport
from contracts.python.soft_launch_client.middleware.correlation import CorrelationMiddleware
from contracts.python.soft_launch_client.middleware.idempotency import IdempotencyMiddleware
from contracts.python.soft_launch_client.middleware.retry import RetryMiddleware


_CAT_INV_OPS: Dict[str, OperationSpec] = {
    "category.create": OperationSpec(service="catalog-inventory", method="POST", path="/catalog/category"),
    "category.get": OperationSpec(service="catalog-inventory", method="GET", path="/catalog/category/{category_id}"),
    "category.list": OperationSpec(service="catalog-inventory", method="GET", path="/catalog/categories"),
    "category.update": OperationSpec(service="catalog-inventory", method="PUT", path="/catalog/category/{category_id}"),
    "category.delete": OperationSpec(service="catalog-inventory", method="DELETE", path="/catalog/category/{category_id}"),

    "product.create": OperationSpec(service="catalog-inventory", method="POST", path="/catalog/product"),
    "product.get": OperationSpec(service="catalog-inventory", method="GET", path="/catalog/product/{product_id}"),
    "product.update": OperationSpec(service="catalog-inventory", method="PUT", path="/catalog/product/{product_id}"),
    "product.delete": OperationSpec(service="catalog-inventory", method="DELETE", path="/catalog/product/{product_id}"),
    "product.add_variant": OperationSpec(service="catalog-inventory", method="POST", path="/catalog/product/{product_id}/variant"),
    "catalog.by_business": OperationSpec(service="catalog-inventory", method="GET", path="/catalog/business/{business_id}"),

    "inventory.update": OperationSpec(service="catalog-inventory", method="POST", path="/inventory/update"),
    "inventory.get": OperationSpec(service="catalog-inventory", method="GET", path="/inventory/{variant_id}"),
}


class CatalogInventoryPlugin:
    """High-level async client for Catalog + Inventory service."""

    def __init__(self, client: AsyncServiceClient) -> None:
        self._client = client

    async def create_category(self, payload: Dict[str, Any]):
        """Create category (POST /catalog/category).

        Parameters:
        - payload: category fields (business_id, name, description, parent_id).

        Returns: Response with category record.
        """
        return await self._client.call("category.create", body=payload)

    async def get_category(self, category_id: str):
        """Get category (GET /catalog/category/{category_id}).

        Parameters:
        - category_id: category identifier.

        Returns: Response with category or 404.
        """
        return await self._client.call("category.get", path_params={"category_id": category_id})

    async def list_categories(self):
        """List categories (GET /catalog/categories).

        Returns: Response with categories array.
        """
        return await self._client.call("category.list")

    async def update_category(self, category_id: str, payload: Dict[str, Any]):
        """Update category (PUT /catalog/category/{category_id}).

        Parameters:
        - category_id: category identifier.
        - payload: fields to update (name, description, parent_id, is_active).

        Returns: Response with updated category.
        """
        return await self._client.call("category.update", path_params={"category_id": category_id}, body=payload)

    async def delete_category(self, category_id: str):
        """Soft-delete category (DELETE /catalog/category/{category_id}).

        Parameters:
        - category_id: category identifier.

        Returns: Response with updated category (is_active=false) or 404.
        """
        return await self._client.call("category.delete", path_params={"category_id": category_id})

    async def create_product(self, payload: Dict[str, Any]):
        """Create product (POST /catalog/product).

        Parameters:
        - payload: product fields (business_id, category_id, name, price, currency, image_url, tags).

        Returns: Response with product record.
        """
        return await self._client.call("product.create", body=payload)

    async def get_product(self, product_id: str):
        """Get product (GET /catalog/product/{product_id}).

        Parameters:
        - product_id: product identifier.

        Returns: Response with product or 404.
        """
        return await self._client.call("product.get", path_params={"product_id": product_id})

    async def update_product(self, product_id: str, payload: Dict[str, Any]):
        """Update product (PUT /catalog/product/{product_id}).

        Parameters:
        - product_id: product identifier.
        - payload: fields to update (price, name, description, image_url, etc.).

        Returns: Response with updated product.
        """
        return await self._client.call("product.update", path_params={"product_id": product_id}, body=payload)

    async def delete_product(self, product_id: str):
        """Delete product (DELETE /catalog/product/{product_id}).

        Parameters:
        - product_id: product identifier.

        Returns: Response confirming deletion.
        """
        return await self._client.call("product.delete", path_params={"product_id": product_id})

    async def add_variant(self, product_id: str, payload: Dict[str, Any]):
        """Add variant (POST /catalog/product/{product_id}/variant).

        Parameters:
        - product_id: product identifier.
        - payload: variant fields (name, sku, price_override).

        Returns: Response with variant record.
        """
        return await self._client.call("product.add_variant", path_params={"product_id": product_id}, body=payload)

    async def catalog_by_business(self, business_id: str):
        """Get catalog by business (GET /catalog/business/{business_id}).

        Parameters:
        - business_id: business identifier.

        Returns: Response with products and variants for the business.
        """
        return await self._client.call("catalog.by_business", path_params={"business_id": business_id})

    async def update_inventory(self, payload: Dict[str, Any]):
        """Update inventory (POST /inventory/update).

        Parameters:
        - payload: variant_id, delta/reserved_delta, threshold, reason/meta.

        Returns: Response with inventory record after update.
        """
        return await self._client.call("inventory.update", body=payload)

    async def get_inventory(self, variant_id: str):
        """Get inventory (GET /inventory/{variant_id}).

        Parameters:
        - variant_id: variant identifier.

        Returns: Response with inventory record or 404.
        """
        return await self._client.call("inventory.get", path_params={"variant_id": variant_id})


def build_default_client(*, base_url: str = "http://127.0.0.1:8520", http_client=None) -> AsyncServiceClient:
    """Build a transport-backed catalog+inventory client with standard middleware."""
    transport = HttpxAsyncTransport(base_urls={"catalog-inventory": base_url}, http=http_client)
    return AsyncServiceClient(
        operation_map=_CAT_INV_OPS,
        transport=transport,
        middlewares=[CorrelationMiddleware(), IdempotencyMiddleware(), RetryMiddleware()],
    )


def build_catalog_inventory_plugin(base_url: str = "http://127.0.0.1:8520", http_client=None) -> CatalogInventoryPlugin:
    """Factory for Catalog + Inventory plugin."""
    return CatalogInventoryPlugin(build_default_client(base_url=base_url, http_client=http_client))
