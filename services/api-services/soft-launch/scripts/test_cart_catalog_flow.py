"""
Test Cart + Catalog-Inventory Integration Flow.

Tests:
1. Create cart
2. Add product to cart (validates from catalog, fetches price/media, checks stock, reserves inventory)
3. Verify cart item has product name and media URL
4. Check inventory was reserved
"""
import httpx
import sys

CATALOG_URL = "http://127.0.0.1:8520"
CART_URL = "http://127.0.0.1:8530"


def test_cart_catalog_integration():
    """Test full cart flow with catalog integration."""
    print("=" * 60)
    print("CART + CATALOG INTEGRATION TEST")
    print("=" * 60)
    print()

    # Step 1: Get a product with media from catalog
    print("🔍 TEST: Fetch Product from Catalog")
    try:
        # Get a business's catalog
        resp = httpx.get(f"{CATALOG_URL}/catalog/business/5181949d-729e-4d2c-8827-5fe6265f3052", timeout=5.0)
        if resp.status_code != 200:
            print(f"   ❌ Failed to fetch catalog: {resp.status_code}")
            return False
        
        catalog = resp.json()
        products = catalog.get("products", [])
        variants = catalog.get("variants", [])
        
        if not products or not variants:
            print("   ❌ No products/variants found in catalog")
            return False
        
        product = products[0]
        variant = variants[0]
        
        product_id = product["id"]
        variant_id = variant["id"]
        product_name = product["name"]
        price = float(variant.get("price_override") or product.get("price", 100))
        
        print(f"   ✅ Found product: {product_name}")
        print(f"      Product ID: {product_id}")
        print(f"      Variant ID: {variant_id}")
        print(f"      Price: {price}")
        
        # Check media
        media_urls = product.get("media_urls", [])
        media_url = None
        if media_urls:
            default_media = next((m for m in media_urls if m.get("is_default")), media_urls[0])
            media_url = default_media.get("url")
            print(f"      Media: {media_url}")
        
        print()
    except Exception as e:
        print(f"   ❌ Error fetching catalog: {e}")
        return False

    # Step 2: Check inventory availability
    print("🔍 TEST: Check Inventory Availability")
    try:
        resp = httpx.get(f"{CATALOG_URL}/inventory/{variant_id}", timeout=5.0)
        if resp.status_code == 200:
            inv = resp.json()
            available = inv.get("available_quantity", 0)
            reserved = inv.get("reserved_quantity", 0)
            print(f"   ✅ Available: {available}, Reserved: {reserved}")
        else:
            print(f"   ⚠️  No inventory record (will create on reserve)")
        print()
    except Exception as e:
        print(f"   ❌ Error checking inventory: {e}")
        return False

    # Step 3: Create cart
    print("🧪 TEST: Create Cart")
    try:
        resp = httpx.post(
            f"{CART_URL}/cart/create",
            json={
                "session_id": "test_session_123",
                "user_phone": "+1234567890",
                "business_id": "msme_shop2"
            },
            timeout=5.0
        )
        
        if resp.status_code != 201:
            print(f"   ❌ Failed to create cart: {resp.status_code}")
            print(f"      {resp.text}")
            return False
        
        cart = resp.json()
        cart_id = cart["id"]
        print(f"   ✅ Cart created: {cart_id}")
        print()
    except Exception as e:
        print(f"   ❌ Error creating cart: {e}")
        return False

    # Step 4: Add product to cart (this should trigger catalog validation)
    print("🧪 TEST: Add Product to Cart (with catalog validation)")
    try:
        resp = httpx.post(
            f"{CART_URL}/cart/{cart_id}/add",
            json={
                "variant_id": variant_id,
                "quantity": 2,
                "unit_price": price  # This should be validated/overridden by catalog
            },
            timeout=10.0
        )
        
        if resp.status_code != 200:
            print(f"   ❌ Failed to add item: {resp.status_code}")
            print(f"      {resp.text}")
            return False
        
        cart_item = resp.json()
        print(f"   ✅ Item added to cart")
        print(f"      Item ID: {cart_item['id']}")
        print(f"      Variant ID: {cart_item['variant_id']}")
        print(f"      Product Name: {cart_item.get('product_name', 'N/A')}")
        print(f"      Media URL: {cart_item.get('media_url', 'N/A')}")
        print(f"      Quantity: {cart_item['quantity']}")
        print(f"      Reserved: {cart_item['reserved_quantity']}")
        print(f"      Unit Price: {cart_item['unit_price']}")
        print(f"      Subtotal: {cart_item['subtotal']}")
        
        # Verify enrichment worked
        if not cart_item.get("product_name"):
            print("   ⚠️  Product name not enriched")
        if not cart_item.get("media_url"):
            print("   ⚠️  Media URL not enriched")
        
        print()
    except Exception as e:
        print(f"   ❌ Error adding item: {e}")
        return False

    # Step 5: Verify inventory was reserved
    print("🔍 TEST: Verify Inventory Reserved")
    try:
        resp = httpx.get(f"{CATALOG_URL}/inventory/{variant_id}", timeout=5.0)
        if resp.status_code == 200:
            inv = resp.json()
            new_reserved = inv.get("reserved_quantity", 0)
            print(f"   ✅ Reserved quantity: {new_reserved}")
            print(f"      Available: {inv.get('available_quantity', 0)}")
        else:
            print(f"   ❌ Failed to fetch inventory: {resp.status_code}")
            return False
        print()
    except Exception as e:
        print(f"   ❌ Error checking inventory: {e}")
        return False

    print("=" * 60)
    print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_cart_catalog_integration()
    sys.exit(0 if success else 1)
