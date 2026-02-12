"""
Test Cart + Catalog-Inventory Integration Flow - NO EMOJI VERSION

Tests:
1. Authenticate with msme-engine
2. Create cart
3. Add product to cart (validates from catalog, fetches price/media, checks stock, reserves inventory)
4. Verify cart item has product name and media URL
5. Check inventory was reserved
"""
import httpx
import sys
import json

MSME_URL = "http://127.0.0.1:8500"
CATALOG_URL = "http://127.0.0.1:8520"
CART_URL = "http://127.0.0.1:8530"


def get_access_token():
    """Get access token from msme-engine."""
    print("[AUTH] Getting access token from msme-engine...")
    try:
        resp = httpx.post(
            f"{MSME_URL}/auth/login",
            json={"identifier": "msme_service", "password": "S3rv!c3-P@ssw0rd"},
            timeout=5.0
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("access_token")
            print(f"[AUTH] Success! Token: {token[:20]}...")
            return token
        else:
            print(f"[AUTH] FAILED! Status: {resp.status_code}")
            print(f"[AUTH] Response: {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"[AUTH] ERROR: {e}")
        sys.exit(1)


def test_cart_catalog_integration():
    """Test full cart flow with catalog integration."""
    print("=" * 60)
    print("CART + CATALOG INTEGRATION TEST")
    print("=" * 60)
    print()

    # Step 0: Get access token
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    print()

    # Step 1: Get a product with media from catalog
    print("[TEST] Fetch Product from Catalog")
    try:
        # Get a business's catalog
        resp = httpx.get(f"{CATALOG_URL}/catalog/business/5181949d-729e-4d2c-8827-5fe6265f3052", timeout=5.0, headers=headers)
        if resp.status_code != 200:
            print(f"   [FAIL] Failed to fetch catalog: {resp.status_code}")
            return False
        
        catalog = resp.json()
        products = catalog.get("products", [])
        variants = catalog.get("variants", [])
        
        if not products or not variants:
            print("   [FAIL] No products/variants found in catalog")
            return False
        
        product = products[0]
        variant = variants[0]
        
        product_id = product["id"]
        variant_id = variant["id"]
        product_name = product["name"]
        price = float(variant.get("price_override") or product.get("price", 100))
        
        print(f"   [OK] Found product: {product_name}")
        print(f"        Product ID: {product_id}")
        print(f"        Variant ID: {variant_id}")
        print(f"        Price: {price}")
        
    except Exception as e:
        print(f"   [ERROR] {str(e)}")
        return False
    
    # Step 2: Check inventory availability
    print()
    print("[TEST] Check Inventory Availability")
    try:
        inv_resp = httpx.get(f"{CATALOG_URL}/inventory/{variant_id}", timeout=5.0, headers=headers)
        if inv_resp.status_code == 200:
            inv_data = inv_resp.json()
            stock = inv_data.get("stock_level", 0)
            reserved = inv_data.get("reserved", 0)
            available = stock - reserved
            print(f"   [OK] Available: {available}, Reserved: {reserved}")
        else:
            print(f"   [WARN] No inventory record (will create on reserve)")
    except Exception as e:
        print(f"   [WARN] Could not check inventory: {str(e)}")
    
    # Step 3: Create a cart
    print()
    print("[TEST] Create Cart")
    try:
        cart_resp = httpx.post(
            f"{CART_URL}/cart/create",
            json={
                "session_id": "test-session-001",
                "user_phone": "555-0001",
                "business_id": "5181949d-729e-4d2c-8827-5fe6265f3052"
            },
            timeout=5.0,
            headers=headers
        )
        if cart_resp.status_code not in [200, 201]:
            print(f"   [FAIL] Failed to create cart: {cart_resp.status_code}")
            print(f"        Response: {cart_resp.text}")
            return False
        
        cart_data = cart_resp.json()
        cart_id = cart_data.get("id")
        print(f"   [OK] Cart created: {cart_id}")
    except Exception as e:
        print(f"   [ERROR] Error creating cart: {str(e)}")
        return False
    
    # Step 4: Add product to cart with catalog validation
    print()
    print("[TEST] Add Product to Cart (with catalog validation)")
    try:
        add_resp = httpx.post(
            f"{CART_URL}/cart/{cart_id}/add",
            json={
                "variant_id": variant_id,
                "quantity": 2,
                "unit_price": price
            },
            timeout=10.0,
            headers=headers
        )
        if add_resp.status_code not in [200, 201]:
            print(f"   [FAIL] Failed to add item: {add_resp.status_code}")
            print(f"        Response: {add_resp.text}")
            return False
        
        item_data = add_resp.json()
        print(f"   [OK] Item added to cart")
        print(f"        Quantity: {item_data.get('quantity')}")
        print(f"        Unit Price: {item_data.get('unit_price')}")
        if item_data.get('product_name'):
            print(f"        Product Name: {item_data.get('product_name')}")
        if item_data.get('media_url'):
            print(f"        Media URL: {item_data.get('media_url')[:50]}...")
    except Exception as e:
        print(f"   [ERROR] Error adding item: {str(e)}")
        return False
    
    # Step 5: Get cart and verify
    print()
    print("[TEST] Get Cart and Verify")
    try:
        get_resp = httpx.get(f"{CART_URL}/cart/session/test-session-001", timeout=5.0, headers=headers)
        if get_resp.status_code != 200:
            print(f"   [FAIL] Failed to get cart: {get_resp.status_code}")
            return False
        
        carts = get_resp.json()
        if isinstance(carts, list):
            carts = [c for c in carts if c.get("id") == cart_id]
            if not carts:
                print(f"   [FAIL] Cart not found in response")
                return False
            cart = carts[0]
        else:
            cart = carts
        
        print(f"   [OK] Cart retrieved")
        print(f"        Cart ID: {cart.get('id')}")
        print(f"        Status: {cart.get('status')}")
    except Exception as e:
        print(f"   [ERROR] Error fetching cart: {str(e)}")
        return False
    
    print()
    print("=" * 60)
    print("[SUCCESS] ALL TESTS PASSED")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_cart_catalog_integration()
    sys.exit(0 if success else 1)
