#!/usr/bin/env python3
"""
Bulk Product Management - Direct Catalog-Inventory API calls
=============================================================
Add 5 products to each of 10 businesses using catalog-inventory service
"""

import httpx
import json
import uuid
import sys

CATALOG_URL = "http://localhost:8520"
MSME_URL = "http://localhost:8500"

# 10 businesses from DB
BUSINESSES = [
    "5181949d-729e-4d2c-8827-5fe6265f3052",
    "5fe78467-a2a8-4e17-9c35-ba5f4e6f449b",
    "0706bb81-73d8-4632-8ed8-64e90b527721",
    "450d4b70-d873-4cf6-8b0f-8f04b1513561",
    "b1b3ef04-5261-430c-8ca0-d972a4dd0f45",
    "592f6bb3-3d89-45be-b990-855f6826498e",
    "40cf0a2a-81d5-4124-9b1b-851b743e7a1c",
    "2b76b181-8b7b-40e8-b098-1239926b7481",
    "fd4ef574-c279-4daa-b1d8-637ff8b7dfe5",
    "ef5d30f3-be90-4013-9101-a65aeb193965",
]

PRODUCTS = [
    {"name": "Laptop Computer", "desc": "High-performance laptop", "price": 450000, "tags": ["electronics", "computers"]},
    {"name": "Wireless Mouse", "desc": "Ergonomic wireless mouse", "price": 25000, "tags": ["electronics", "accessories"]},
    {"name": "USB-C Cable", "desc": "Durable USB-C cable", "price": 8000, "tags": ["accessories", "cable"]},
    {"name": "Mechanical Keyboard", "desc": "RGB mechanical keyboard", "price": 180000, "tags": ["electronics", "keyboard"]},
    {"name": "USB Hub", "desc": "7-port USB 3.0 hub", "price": 50000, "tags": ["electronics", "hub"]},
]

stats = {"businesses": 0, "categories": 0, "products": 0, "variants": 0, "inventory": 0, "errors": 0}


def get_token():
    """Get auth token by creating a test user."""
    username = f"bulk_{uuid.uuid4().hex[:8]}"
    with httpx.Client(timeout=10) as client:
        r = client.post(f"{MSME_URL}/auth/register", json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "Test@12345",
            "phone": "+260970000001",
        })
        if r.status_code not in [200, 201]:
            print(f"ERROR: Register failed {r.status_code}")
            return None
        
        r = client.post(f"{MSME_URL}/auth/login", json={
            "identifier": username,
            "password": "Test@12345",
        })
        if r.status_code != 200:
            print(f"ERROR: Login failed {r.status_code}")
            return None
        
        return r.json()["access_token"]


def add_products_to_business(business_id, token):
    """Add 5 products to a business."""
    headers = {"Authorization": f"Bearer {token}"}
    
    with httpx.Client(timeout=15) as client:
        # Create category
        r = client.post(f"{CATALOG_URL}/catalog/category", json={
            "business_id": business_id,
            "name": f"Electronics-{uuid.uuid4().hex[:4]}",
            "description": "Electronics and gadgets",
        }, headers=headers)
        
        if r.status_code != 201:
            print(f"  ERROR: Category creation failed {r.status_code}")
            stats["errors"] += 1
            return 0
        
        category_id = r.json()["id"]
        stats["categories"] += 1
        
        products_added = 0
        for product in PRODUCTS:
            # Create product
            r = client.post(f"{CATALOG_URL}/catalog/product", json={
                "business_id": business_id,
                "category_id": category_id,
                "name": product["name"],
                "description": product["desc"],
                "price": product["price"],
                "currency": "ZMW",
                "image_url": None,
                "tags": product["tags"],
            }, headers=headers)
            
            if r.status_code != 201:
                print(f"    WARN: Product '{product['name']}' failed {r.status_code}")
                stats["errors"] += 1
                continue
            
            product_id = r.json()["id"]
            stats["products"] += 1
            
            # Create variant
            r = client.post(f"{CATALOG_URL}/catalog/product/{product_id}/variant", json={
                "name": "Standard",
                "sku": f"SKU-{uuid.uuid4().hex[:8].upper()}",
                "price_override": None,
            }, headers=headers)
            
            if r.status_code != 201:
                print(f"    WARN: Variant for '{product['name']}' failed {r.status_code}")
                stats["errors"] += 1
                continue
            
            variant_id = r.json()["id"]
            stats["variants"] += 1
            
            # Add inventory
            r = client.post(f"{CATALOG_URL}/inventory/update", json={
                "variant_id": variant_id,
                "delta": 50,
                "reserved_delta": 0,
                "threshold": 10,
                "reason": "bulk_initial_stock",
                "meta": {"source": "bulk_script"},
            }, headers=headers)
            
            if r.status_code == 200:
                stats["inventory"] += 1
                products_added += 1
            else:
                print(f"    WARN: Inventory for '{product['name']}' failed {r.status_code}")
                stats["errors"] += 1
    
    return products_added


def main():
    print("\n" + "=" * 80)
    print("BULK PRODUCT MANAGEMENT - 10 Businesses x 5 Products")
    print("=" * 80)
    
    # Get auth token
    print("\nGetting auth token...")
    token = get_token()
    if not token:
        print("ERROR: Failed to get token")
        sys.exit(1)
    
    print(f"Token obtained: {token[:20]}...\n")
    
    # Process each business
    for idx, business_id in enumerate(BUSINESSES, 1):
        print(f"[{idx}/10] Processing {business_id[:8]}...", end=" ")
        count = add_products_to_business(business_id, token)
        stats["businesses"] += 1
        print(f"{count}/5 products added")
    
    # Summary
    print("\n" + "=" * 80)
    print("BULK SIMULATION COMPLETE")
    print("=" * 80)
    print(json.dumps(stats, indent=2))
    print("=" * 80)


if __name__ == "__main__":
    main()
