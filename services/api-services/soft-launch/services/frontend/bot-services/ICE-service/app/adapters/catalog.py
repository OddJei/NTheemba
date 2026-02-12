"""Catalog/Inventory adapter (HTTP-backed for catalog-inventory service)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import aiohttp

from .base import CatalogAdapter

logger = logging.getLogger(__name__)


class CatalogInventoryAdapter(CatalogAdapter):
    def __init__(self, base_url: Optional[str] = None, timeout: float = 5.0):
        self.base_url = base_url
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
        self.use_http = base_url is not None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self._session

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def health_check(self) -> bool:
        if not self.use_http:
            return False
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/health") as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Catalog health check failed: {e}")
            return False

    async def fetch_product_snapshot(self, business_id: str, product_id: str) -> Dict[str, Any]:
        """Fetch a single product with its variants and inventory availability."""
        if not self.use_http:
            return {"status": "FAILED", "reason": "CATALOG_SERVICE_NOT_CONFIGURED"}

        session = await self._get_session()

        # Get product details
        async with session.get(f"{self.base_url}/catalog/product/{product_id}") as resp:
            if resp.status != 200:
                return {"status": "FAILED", "reason": f"PRODUCT_NOT_FOUND_HTTP_{resp.status}"}
            product = await resp.json()

        # Get business catalog to find variants for this product
        async with session.get(f"{self.base_url}/catalog/business/{business_id}") as resp:
            if resp.status != 200:
                return {"status": "FAILED", "reason": f"CATALOG_FETCH_HTTP_{resp.status}"}
            catalog = await resp.json()

        # Filter variants for this product
        variants = [v for v in catalog.get("variants", []) if v.get("product_id") == product_id]

        # Fetch inventory for each variant
        inventory_data = []
        for variant in variants:
            variant_id = variant.get("id")
            async with session.get(f"{self.base_url}/inventory/{variant_id}") as inv_resp:
                if inv_resp.status == 200:
                    inv = await inv_resp.json()
                    inventory_data.append({
                        "variant_id": variant_id,
                        "variant_name": variant.get("name"),
                        "sku": variant.get("sku"),
                        "stock_level": inv.get("stock_level", 0),
                        "reserved": inv.get("reserved", 0),
                        "available": inv.get("stock_level", 0) - inv.get("reserved", 0),
                        "in_stock": (inv.get("stock_level", 0) - inv.get("reserved", 0)) > 0,
                    })
                else:
                    inventory_data.append({
                        "variant_id": variant_id,
                        "variant_name": variant.get("name"),
                        "sku": variant.get("sku"),
                        "stock_level": 0,
                        "reserved": 0,
                        "available": 0,
                        "in_stock": False,
                    })

        return {
            "product": product,
            "variants": variants,
            "inventory": inventory_data,
        }

    async def fetch_catalog_index(self, business_id: str) -> Dict[str, Any]:
        """Fetch full catalog for a business including products and variants."""
        if not self.use_http:
            return {"status": "FAILED", "reason": "CATALOG_SERVICE_NOT_CONFIGURED"}

        session = await self._get_session()

        async with session.get(f"{self.base_url}/catalog/business/{business_id}") as resp:
            if resp.status != 200:
                return {"status": "FAILED", "reason": f"HTTP_{resp.status}"}
            catalog = await resp.json()

        # Optionally enrich with inventory for all variants
        variants = catalog.get("variants", [])
        for variant in variants:
            variant_id = variant.get("id")
            async with session.get(f"{self.base_url}/inventory/{variant_id}") as inv_resp:
                if inv_resp.status == 200:
                    inv = await inv_resp.json()
                    variant["stock_level"] = inv.get("stock_level", 0)
                    variant["reserved"] = inv.get("reserved", 0)
                    variant["available"] = inv.get("stock_level", 0) - inv.get("reserved", 0)
                    variant["in_stock"] = variant["available"] > 0
                else:
                    variant["stock_level"] = 0
                    variant["reserved"] = 0
                    variant["available"] = 0
                    variant["in_stock"] = False

        return catalog
