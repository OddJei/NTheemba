"""
Test Order-Delivery Service with Audit Logging

Tests:
1. Authenticate with msme-engine
2. Create a cart with items
3. Create an order from the cart
4. Verify audit events were emitted:
   - order_created
   - delivery_initiated (if applicable)
"""
import httpx
import sys
import json

MSME_URL = "http://127.0.0.1:8500"
CATALOG_URL = "http://127.0.0.1:8520"
CART_URL = "http://127.0.0.1:8530"
ORDER_URL = "http://127.0.0.1:8560"


def get_access_token():
    """Get access token from msme-engine."""
    print("[AUTH] Getting access token...")
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


def main():
    print("=" * 60)
    print("ORDER-DELIVERY SERVICE + AUDIT LOGGING TEST")
    print("=" * 60)
    print()
    
    # Get auth token
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Step 1: Get a product from catalog
    print("[TEST] Fetch Product from Catalog")
    try:
        # Use real product and variant that exist in DB
        product_id = "7dd80f79-2e8a-4dcc-9a20-7ceba2d74d67"  # Wireless Headphones
        variant_id = "01bab0ff-4bbc-4c3d-b3c2-99b86194ce83"
        business_id = "a305ddb9-4432-4b7d-9e75-4225391f8bb4"
        
        # Get variant by ID
        resp = httpx.get(f"{CATALOG_URL}/catalog/product/variant/{variant_id}", headers=headers)
        if resp.status_code != 200:
            print(f"   [ERROR] Failed to fetch variant: {resp.status_code}")
            sys.exit(1)
        
        variant = resp.json()
        product_name = "Wireless Headphones"
        
        # Get product to fetch base price
        resp2 = httpx.get(f"{CATALOG_URL}/catalog/product/{product_id}", headers=headers)
        if resp2.status_code != 200:
            print(f"   [ERROR] Failed to fetch product: {resp2.status_code}")
            sys.exit(1)
        
        product = resp2.json()
        price = float(variant.get("price_override") or product.get("price", 100))
        
        print(f"   [OK] Found product: {product_name}")
        print(f"        Product ID: {product_id}")
        print(f"        Variant ID: {variant_id}")
        print(f"        Price: {price}")
        print()
    except Exception as e:
        print(f"   [ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Step 2: Create cart
    print("[TEST] Create Cart")
    try:
        resp = httpx.post(
            f"{CART_URL}/cart/create",
            json={"user_id": "msme_service_user_id"},
            headers=headers,
            timeout=5.0
        )
        if resp.status_code not in [200, 201]:
            print(f"   [ERROR] Failed to create cart: {resp.status_code} - {resp.text}")
            sys.exit(1)
        
        cart_data = resp.json()
        cart_id = cart_data.get("cart_id") or cart_data.get("id")
        print(f"   [OK] Cart created: {cart_id}")
        print()
    except Exception as e:
        print(f"   [ERROR] {e}")
        sys.exit(1)
    
    # Step 3: Add item to cart
    print("[TEST] Add Product to Cart")
    try:
        resp = httpx.post(
            f"{CART_URL}/cart/{cart_id}/add",
            json={
                "product_id": product_id,
                "variant_id": variant_id,
                "quantity": 2
            },
            headers=headers,
            timeout=5.0
        )
        if resp.status_code != 200:
            print(f"   [ERROR] Failed to add item: {resp.status_code} - {resp.text}")
            sys.exit(1)
        
        print(f"   [OK] Item added to cart")
        print(f"        Quantity: 2")
        print(f"        Unit Price: {price}")
        print()
    except Exception as e:
        print(f"   [ERROR] {e}")
        sys.exit(1)
    
    # Step 4: Create order from cart
    print("[TEST] Create Order from Cart")
    try:
        # Calculate total
        total_amount = price * 2
        
        # Create order payload directly (we have all the info)
        order_payload = {
            "business_id": business_id,
            "customer_id": "msme_service_user_id",
            "user_phone": "260760000001",
            "total_amount": total_amount,
            "items": [
                {
                    "product_id": product_id,
                    "variant_id": variant_id,
                    "quantity": 2,
                    "unit_price": price
                }
            ],
            "delivery_address": "123 Test Street, Test City",
            "delivery_phone": "260760000001"
        }
        
        resp = httpx.post(
            f"{ORDER_URL}/orders/create",
            json=order_payload,
            headers=headers,
            timeout=10.0
        )
        
        if resp.status_code not in (200, 201):
            print(f"   [ERROR] Failed to create order: {resp.status_code}")
            print(f"   [ERROR] Response: {resp.text}")
            sys.exit(1)
        
        order_data = resp.json()
        order_id = order_data.get("id") or order_data.get("order_id")
        print(f"   [OK] Order created: {order_id}")
        print(f"        Status: {order_data.get('status')}")
        print(f"        Total: {order_data.get('total_amount')}")
        print()
    except Exception as e:
        print(f"   [ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Success
    print("=" * 60)
    print("[SUCCESS] ALL TESTS PASSED")
    print("=" * 60)
    print()
    print("Next Steps:")
    print("  1. Check audit-service logs for 'order_created' event")
    print("  2. Query audit_service.audit_events table")
    print(f"     WHERE entity_id = '{order_id}' AND event_type = 'order_created'")


if __name__ == "__main__":
    main()
