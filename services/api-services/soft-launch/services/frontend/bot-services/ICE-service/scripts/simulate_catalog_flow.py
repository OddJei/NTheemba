"""Integration simulation for catalog/inventory adapter.

Tests fetching product snapshots and checking inventory availability.
Requires catalog-inventory service running (Docker).
"""

import asyncio
import logging
from pprint import pprint

from app.adapters.factory import AdapterFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    catalog_adapter = AdapterFactory.get_catalog_adapter()

    # Health check
    is_healthy = await catalog_adapter.health_check()
    logger.info(f"Catalog service health: {is_healthy}")

    if not is_healthy:
        logger.warning("Catalog service unavailable")
        await AdapterFactory.cleanup()
        return

    # Test 1: Fetch business catalog index
    logger.info("\n=== Test 1: Fetch Business Catalog Index ===")
    business_id = "BIZ-001"
    catalog = await catalog_adapter.fetch_catalog_index(business_id)
    
    if catalog.get("status") == "FAILED":
        logger.error(f"Failed to fetch catalog: {catalog.get('reason')}")
    else:
        logger.info(f"Business: {catalog.get('business_id')}")
        logger.info(f"Products count: {len(catalog.get('products', []))}")
        logger.info(f"Variants count: {len(catalog.get('variants', []))}")
        
        # Show first product if available
        products = catalog.get("products", [])
        if products:
            logger.info("\nFirst product:")
            pprint(products[0])
        
        # Show variant inventory
        variants = catalog.get("variants", [])
        if variants:
            logger.info("\nVariants with inventory:")
            for v in variants[:3]:  # Show first 3
                logger.info(f"  - {v.get('name')} (SKU: {v.get('sku')}): "
                          f"stock={v.get('stock_level', 0)}, "
                          f"reserved={v.get('reserved', 0)}, "
                          f"available={v.get('available', 0)}, "
                          f"in_stock={v.get('in_stock', False)}")

    # Test 2: Fetch specific product snapshot
    if catalog.get("products"):
        product_id = catalog["products"][0].get("id")
        logger.info(f"\n=== Test 2: Fetch Product Snapshot (ID: {product_id}) ===")
        
        snapshot = await catalog_adapter.fetch_product_snapshot(business_id, product_id)
        
        if snapshot.get("status") == "FAILED":
            logger.error(f"Failed to fetch product: {snapshot.get('reason')}")
        else:
            product = snapshot.get("product", {})
            logger.info(f"Product: {product.get('name')}")
            logger.info(f"Price: {product.get('price')} {product.get('currency')}")
            logger.info(f"Active: {product.get('is_active')}")
            
            inventory = snapshot.get("inventory", [])
            logger.info(f"\nInventory ({len(inventory)} variants):")
            for inv in inventory:
                logger.info(f"  - {inv.get('variant_name')}: "
                          f"available={inv.get('available')}, "
                          f"in_stock={inv.get('in_stock')}")

    await AdapterFactory.cleanup()
    logger.info("\n✓ Catalog integration test complete")


if __name__ == "__main__":
    asyncio.run(main())
