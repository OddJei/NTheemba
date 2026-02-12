"""Seed test catalog data and test inventory availability.

This script:
1. Creates a test product
2. Creates variants for the product
3. Sets inventory levels
4. Tests availability checking

Prerequisites:
- Catalog service must be running with CATALOG_SKIP_MSME_VALIDATION=1
- Set via: docker restart soft-launch-catalog-inventory-1 -e CATALOG_SKIP_MSME_VALIDATION=1
"""

import asyncio
import logging
from pprint import pprint
from uuid import uuid4

import aiohttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8520"
BUSINESS_ID = "BIZ-001"


async def main() -> None:
    # Auth headers for catalog service
    headers = {
        "Authorization": "Bearer dummy-token",
        "X-Role": "vendor",
        "X-Business-Id": BUSINESS_ID,
        "X-Idempotency-Key": str(uuid4()),
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        # Create a product
        logger.info("Creating test product...")
        product_payload = {
            "business_id": BUSINESS_ID,
            "name": "Test Product - Laptop",
            "description": "High-performance laptop",
            "price": 5000.00,
            "currency": "ZMW",
            "tags": ["electronics", "computers"],
        }
        
        async with session.post(f"{BASE_URL}/catalog/product", json=product_payload) as resp:
            if resp.status not in (200, 201):
                error_detail = await resp.text()
                logger.error(f"Failed to create product: {resp.status} - {error_detail}")
                return
            product = await resp.json()
            product_id = product["id"]
            logger.info(f"✓ Created product: {product['name']} (ID: {product_id})")

        # Create variants
        logger.info("\nCreating variants...")
        variants_data = [
            {"name": "16GB RAM", "sku": "LAP-16GB", "price_override": 5500.00},
            {"name": "32GB RAM", "sku": "LAP-32GB", "price_override": 6500.00},
            {"name": "64GB RAM - Out of Stock", "sku": "LAP-64GB-OOS", "price_override": 8500.00},
        ]
        
        variant_ids = []
        for vdata in variants_data:
            async with session.post(
                f"{BASE_URL}/catalog/product/{product_id}/variant",
                json=vdata
            ) as resp:
                if resp.status in (200, 201):
                    variant = await resp.json()
                    variant_ids.append(variant["id"])
                    logger.info(f"  ✓ Created variant: {variant['name']} (SKU: {variant['sku']})")

        # Set inventory levels
        logger.info("\nSetting inventory levels...")
        inventory_updates = [
            {"variant_id": variant_ids[0], "delta": 10, "threshold": 3},  # In stock
            {"variant_id": variant_ids[1], "delta": 5, "threshold": 2},   # In stock
            {"variant_id": variant_ids[2], "delta": 0, "threshold": 1},   # Out of stock
        ]
        
        for inv_update in inventory_updates:
            async with session.post(f"{BASE_URL}/inventory/update", json=inv_update) as resp:
                if resp.status == 200:
                    inv = await resp.json()
                    logger.info(f"  ✓ Set inventory for variant {inv_update['variant_id'][:8]}...: "
                              f"stock={inv['stock_level']}, reserved={inv['reserved']}")

        # Test availability via catalog adapter
        logger.info("\n=== Testing Catalog Adapter ===")
        from app.adapters.factory import AdapterFactory
        
        catalog_adapter = AdapterFactory.get_catalog_adapter()
        
        # Fetch product snapshot with inventory
        snapshot = await catalog_adapter.fetch_product_snapshot(BUSINESS_ID, product_id)
        
        logger.info(f"\nProduct Snapshot:")
        logger.info(f"  Name: {snapshot['product']['name']}")
        logger.info(f"  Price: {snapshot['product']['price']} {snapshot['product']['currency']}")
        logger.info(f"\nInventory Availability:")
        for inv in snapshot["inventory"]:
            status = "✓ IN STOCK" if inv["in_stock"] else "✗ OUT OF STOCK"
            logger.info(f"  {inv['variant_name']} (SKU: {inv['sku']}): {status}")
            logger.info(f"    Stock: {inv['stock_level']}, Reserved: {inv['reserved']}, "
                       f"Available: {inv['available']}")

        # Fetch full catalog
        logger.info("\n=== Full Catalog Index ===")
        catalog = await catalog_adapter.fetch_catalog_index(BUSINESS_ID)
        logger.info(f"Total products: {len(catalog.get('products', []))}")
        logger.info(f"Total variants: {len(catalog.get('variants', []))}")
        
        in_stock_count = sum(1 for v in catalog.get("variants", []) if v.get("in_stock"))
        logger.info(f"In-stock variants: {in_stock_count}/{len(catalog.get('variants', []))}")

        await AdapterFactory.cleanup()
        logger.info("\n✓ Catalog test complete")


if __name__ == "__main__":
    asyncio.run(main())
