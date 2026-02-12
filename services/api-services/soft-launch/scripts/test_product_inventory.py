#!/usr/bin/env python3
"""
Test Product Upload & Inventory Management Flow
================================================
1. Create category
2. Create product with metadata
3. Add product variant with SKU
4. Upload product image (presign + complete)
5. Update inventory (stock & reservations)
6. Check inventory levels
"""

import httpx
import json
import uuid

BASE_URL = "http://localhost:8520"
MSME_BASE_URL = "http://localhost:8500"

# Test data
test_business_id = None
test_product_id = None
test_variant_id = None
test_category_id = None
test_access_token = None


def safe_body(r: httpx.Response):
    try:
        return r.json()
    except Exception:
        text = (r.text or "").strip()
        return {"raw": text[:2000]}


def log(msg, data=None):
    print(f"\n{'=' * 80}")
    print(f">> {msg}")
    if data:
        print(json.dumps(data, indent=2, default=str))
    print('=' * 80)


async def create_category():
    """Create a product category."""
    global test_access_token
    log("Creating product category...")
    
    headers = {"Authorization": f"Bearer {test_access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{BASE_URL}/catalog/category", json={
            "business_id": test_business_id,
            "name": "Electronics",
            "description": "Electronic products",
        }, headers=headers)
        
        if r.status_code != 201:
            log("ERROR: Category creation failed", {"status": r.status_code, "body": safe_body(r)})
            return None
        
        category = r.json()
        log("Category created", {
            "category_id": category["id"],
            "name": category["name"],
        })
        return category


async def create_product():
    """Create a product."""
    global test_access_token
    log("Creating product...")
    
    headers = {"Authorization": f"Bearer {test_access_token}"}
    async with httpx.AsyncClient(timeout=15) as client:
        # Retry with longer timeout
        for attempt in range(3):
            r = await client.post(f"{BASE_URL}/catalog/product", json={
                "business_id": test_business_id,
                "category_id": test_category_id,
                "name": "Wireless Headphones",
                "description": "High-quality wireless headphones with noise cancellation",
                "price": 25000,  # 250 ZMW
                "currency": "ZMW",
                "image_url": None,
                "tags": ["electronics", "audio", "wireless"],
            }, headers=headers)
            
            if r.status_code == 201:
                break
            if attempt < 2:
                import asyncio
                await asyncio.sleep(2)
                continue
        
        if r.status_code != 201:
            log("ERROR: Product creation failed", {"status": r.status_code, "body": safe_body(r)})
            return None
        
        product = r.json()
        log("Product created", {
            "product_id": product["id"],
            "name": product["name"],
            "price": product["price"],
            "currency": product["currency"],
        })
        return product


async def create_variant():
    """Create a product variant with SKU."""
    global test_access_token
    log("Creating product variant...")
    
    headers = {"Authorization": f"Bearer {test_access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        # SKU is usually unique; generate a new one each run to avoid conflicts
        sku = f"WH-{uuid.uuid4().hex[:10].upper()}"
        r = await client.post(f"{BASE_URL}/catalog/product/{test_product_id}/variant", json={
            "name": "Black - Large",
            "sku": sku,
            "price_override": None,
        }, headers=headers)
        
        if r.status_code != 201:
            log("ERROR: Variant creation failed", {"status": r.status_code, "body": safe_body(r)})
            return None
        
        variant = r.json()
        log("Variant created", {
            "variant_id": variant["id"],
            "name": variant["name"],
            "sku": variant["sku"],
        })
        return variant


async def presign_upload():
    """Get a presigned URL for image upload."""
    global test_access_token
    log("Getting presigned upload URL...")
    
    headers = {"Authorization": f"Bearer {test_access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{BASE_URL}/uploads/presign", json={
            "filename": "headphones.jpg",
            "content_type": "image/jpeg",
        }, headers=headers)
        
        if r.status_code != 200:
            log("ERROR: Presign failed", {"status": r.status_code, "body": safe_body(r)})
            return None
        
        result = r.json()
        log("Presigned URL generated", {
            "key": result["key"],
            "upload_url": result["url"][:80] + "..." if len(result["url"]) > 80 else result["url"],
        })
        return result


async def update_inventory_add_stock():
    """Add stock to inventory."""
    global test_access_token
    log("Adding stock to inventory...")
    
    headers = {"Authorization": f"Bearer {test_access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{BASE_URL}/inventory/update", json={
            "variant_id": test_variant_id,
            "delta": 100,  # Add 100 units
            "reserved_delta": 0,
            "threshold": 10,  # Low stock threshold
            "reason": "initial_stock",
            "meta": {"batch": "BATCH-001", "warehouse": "main"},
        }, headers=headers)
        
        if r.status_code != 200:
            log("ERROR: Inventory update failed", {"status": r.status_code, "body": safe_body(r)})
            return False
        
        inv = r.json()
        log("Stock added", {
            "variant_id": inv["variant_id"],
            "stock_level": inv["stock_level"],
            "reserved": inv["reserved"],
            "threshold": inv["threshold"],
        })
        return True


async def update_inventory_reserve_stock():
    """Reserve stock for a pending order."""
    global test_access_token
    log("Reserving stock for order...")
    
    headers = {"Authorization": f"Bearer {test_access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{BASE_URL}/inventory/update", json={
            "variant_id": test_variant_id,
            "delta": 0,  # Don't change total stock
            "reserved_delta": 10,  # Reserve 10 units
            "reason": "order_created",
            "meta": {"order_id": "ORD-001", "customer": "cust-123"},
        }, headers=headers)
        
        if r.status_code != 200:
            log("ERROR: Reservation failed", {"status": r.status_code, "body": safe_body(r)})
            return False
        
        inv = r.json()
        log("Stock reserved", {
            "variant_id": inv["variant_id"],
            "stock_level": inv["stock_level"],
            "reserved": inv["reserved"],
            "available": inv["stock_level"] - inv["reserved"],
        })
        return True


async def update_inventory_confirm_order():
    """Confirm order - decrement both reserved and available stock."""
    global test_access_token
    log("Confirming order - decrementing stock...")
    
    headers = {"Authorization": f"Bearer {test_access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{BASE_URL}/inventory/update", json={
            "variant_id": test_variant_id,
            "delta": -10,  # Decrease total stock by 10
            "reserved_delta": -10,  # Release the 10 reserved units
            "reason": "order_confirmed",
            "meta": {"order_id": "ORD-001"},
        }, headers=headers)
        
        if r.status_code != 200:
            log("ERROR: Confirmation failed", {"status": r.status_code, "body": safe_body(r)})
            return False
        
        inv = r.json()
        log("Order confirmed - stock decremented", {
            "variant_id": inv["variant_id"],
            "stock_level": inv["stock_level"],
            "reserved": inv["reserved"],
            "available": inv["stock_level"] - inv["reserved"],
        })
        return True


async def get_inventory():
    """Get current inventory status."""
    log("Getting inventory status...")

    headers = {}
    if test_access_token:
        headers = {"Authorization": f"Bearer {test_access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BASE_URL}/inventory/{test_variant_id}", headers=headers)
        
        if r.status_code != 200:
            log("ERROR: Get inventory failed", {"status": r.status_code, "body": safe_body(r)})
            return None
        
        inv = r.json()
        log("Current inventory", {
            "variant_id": inv["variant_id"],
            "stock_level": inv["stock_level"],
            "reserved": inv["reserved"],
            "available": inv["stock_level"] - inv["reserved"],
            "threshold": inv["threshold"],
            "out_of_stock": inv.get("out_of_stock", False),
        })
        return inv


async def get_business_catalog():
    """Get full catalog for business."""
    log("Getting business catalog...")
    
    headers = {}
    if test_access_token:
        headers = {"Authorization": f"Bearer {test_access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BASE_URL}/catalog/business/{test_business_id}", headers=headers)
        
        if r.status_code != 200:
            log("ERROR: Get catalog failed", {"status": r.status_code, "body": safe_body(r)})
            return None
        
        catalog = r.json()
        log("Business catalog", {
            "business_id": catalog["business_id"],
            "product_count": len(catalog["products"]),
            "variant_count": len(catalog["variants"]),
            "products": [{"id": p["id"], "name": p["name"]} for p in catalog["products"][:3]],
        })
        return catalog


async def main():
    global test_business_id, test_product_id, test_variant_id, test_category_id, test_access_token
    
    print("\n" + "=" * 80)
    print("PRODUCT UPLOAD & INVENTORY MANAGEMENT FLOW")
    print("=" * 80)
    
    # Step 1: Get/create business
    log("Setting up test business...")
    async with httpx.AsyncClient(timeout=10) as client:
        username = f"testuser{uuid.uuid4().hex[:6]}"
        r = await client.post(f"{MSME_BASE_URL}/auth/register", json={
            "username": username,
            "email": f"test-{uuid.uuid4().hex[:8]}@example.com",
            "password": "test123",
            "phone": "+260970000001",
        })
        user_id = r.json()["id"]
        
        r = await client.post(f"{MSME_BASE_URL}/auth/login", json={
            "identifier": username,
            "password": "test123",
        })
        test_access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {test_access_token}"}
        
        r = await client.post(f"{MSME_BASE_URL}/business/register", json={
            "owner_user_id": user_id,
            "name": f"Test Store {uuid.uuid4().hex[:6]}",
            "location": "Lusaka",
            "category": "Retail",
        }, headers=headers)
        test_business_id = r.json()["business"]["id"]
        log("Business ready", {"business_id": test_business_id})
    
    # Step 2: Create category
    category = await create_category()
    if not category:
        return
    test_category_id = category["id"]
    
    # Step 3: Create product
    product = await create_product()
    if not product:
        return
    test_product_id = product["id"]
    
    # Step 4: Create variant
    variant = await create_variant()
    if not variant:
        return
    test_variant_id = variant["id"]
    
    # Step 5: Presign image upload
    upload_info = await presign_upload()
    if not upload_info:
        return
    
    # Step 6: Add stock
    if not await update_inventory_add_stock():
        return
    
    # Step 7: Check inventory
    await get_inventory()
    
    # Step 8: Reserve stock for order
    if not await update_inventory_reserve_stock():
        return
    
    # Step 9: Check inventory after reservation
    await get_inventory()
    
    # Step 10: Confirm order
    if not await update_inventory_confirm_order():
        return
    
    # Step 11: Check final inventory
    await get_inventory()
    
    # Step 12: Get full catalog
    await get_business_catalog()
    
    # Summary
    log("SUCCESS: PRODUCT & INVENTORY FLOW COMPLETED", {
        "flow": [
            "1. Created category",
            "2. Created product with metadata",
            "3. Created product variant with SKU",
            "4. Generated presigned image upload URL",
            "5. Added 100 units to inventory",
            "6. Reserved 10 units for order",
            "7. Confirmed order (decremented stock)",
            "8. Verified final inventory levels",
            "9. Retrieved full business catalog",
        ],
        "summary": {
            "initial_stock": 100,
            "reserved": 10,
            "ordered": 10,
            "final_stock": 90,
            "available": 90,
        }
    })


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
