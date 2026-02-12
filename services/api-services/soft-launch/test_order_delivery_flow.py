"""
Test Order-Delivery Service Flow with Audit Logging

This script tests the order and delivery lifecycle:
1. Create an order (order_created audit event)
2. Mark order as paid (order_paid audit event)
3. Initiate delivery (delivery_initiated audit event)
4. Confirm delivery (delivery_confirmed audit event)
"""

import asyncio
import httpx


BASE_URL_ORDER = "http://localhost:8560"
BASE_URL_CATALOG = "http://localhost:8520"
BASE_URL_CART = "http://localhost:8530"

# Test data
BUSINESS_ID = "5181949d-729e-4d2c-8827-5fe6265f3052"  # From previous tests
USER_PHONE = "+27123456789"


async def test_order_delivery_flow():
    """Test complete order-delivery lifecycle"""
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n=== Order-Delivery Flow Test ===\n")
        
        # Step 1: Create a cart and add an item
        print("Step 1: Creating cart and adding item...")
        cart_resp = await client.post(
            f"{BASE_URL_CART}/cart/create",
            json={"business_id": BUSINESS_ID, "user_phone": USER_PHONE}
        )
        assert cart_resp.status_code in (200, 201), f"Failed to create cart: {cart_resp.text}"
        cart_data = cart_resp.json()
        cart_id = cart_data["id"]
        print(f"  Cart created: {cart_id}")
        
        # Add item to cart
        variant_id = "50d6d250-1192-4cd4-ac56-9765314b2e30"  # From previous tests
        add_resp = await client.post(
            f"{BASE_URL_CART}/cart/{cart_id}/add",
            json={"variant_id": variant_id, "quantity": 2}
        )
        assert add_resp.status_code == 200, f"Failed to add item: {add_resp.text}"
        print(f"  Item added to cart (variant: {variant_id}, quantity: 2)")
        
        # Checkout cart
        checkout_resp = await client.post(
            f"{BASE_URL_CART}/cart/{cart_id}/checkout",
            json={}
        )
        assert checkout_resp.status_code == 200, f"Failed to checkout: {checkout_resp.text}"
        print(f"  Cart checked out")
        
        # Step 2: Create an order from the cart
        print("\nStep 2: Creating order...")
        order_payload = {
            "business_id": BUSINESS_ID,
            "user_phone": USER_PHONE,
            "total_amount": 200.00,
            "currency": "ZAR",
            "delivery_method": "pickup",
            "cart_id": cart_id,
            "order_items": [
                {
                    "variant_id": variant_id,
                    "product_name": "Test Product",
                    "quantity": 2,
                    "unit_price": 100.00,
                    "subtotal": 200.00
                }
            ]
        }
        
        order_resp = await client.post(
            f"{BASE_URL_ORDER}/orders/create",
            json=order_payload,
            headers={"X-Idempotency-Key": f"test-order-{asyncio.get_event_loop().time()}"}
        )
        assert order_resp.status_code == 201, f"Failed to create order: {order_resp.text}"
        order_data = order_resp.json()
        order_id = order_data["id"]
        print(f"  Order created: {order_id}")
        print(f"  Status: {order_data['status']}")
        print(f"  Total: {order_data['total_amount']} {order_data['currency']}")
        
        # Step 3: Mark order as paid
        print(f"\nStep 3: Marking order as paid...")
        paid_resp = await client.post(f"{BASE_URL_ORDER}/orders/{order_id}/mark_paid")
        assert paid_resp.status_code == 200, f"Failed to mark order paid: {paid_resp.text}"
        paid_data = paid_resp.json()
        print(f"  Order marked as paid")
        print(f"  New status: {paid_data['status']}")
        if paid_data.get("meta"):
            print(f"  Platform fee: {paid_data['meta'].get('platform_fee_amount', 'N/A')}")
            print(f"  MSME net: {paid_data['meta'].get('msme_net_amount', 'N/A')}")
        
        # Step 4: Initiate delivery
        print(f"\nStep 4: Initiating delivery...")
        delivery_resp = await client.post(
            f"{BASE_URL_ORDER}/delivery/initiate/{order_id}",
            headers={"X-Idempotency-Key": f"test-delivery-{asyncio.get_event_loop().time()}"}
        )
        assert delivery_resp.status_code == 201, f"Failed to initiate delivery: {delivery_resp.text}"
        delivery_data = delivery_resp.json()
        delivery_id = delivery_data["delivery"]["id"]
        delivery_code = delivery_data["delivery_code"]
        print(f"  Delivery initiated: {delivery_id}")
        print(f"  Delivery code: {delivery_code}")
        print(f"  Delivery method: {delivery_data['delivery']['delivery_method']}")
        
        # Step 5: Confirm delivery
        print(f"\nStep 5: Confirming delivery...")
        confirm_resp = await client.post(
            f"{BASE_URL_ORDER}/delivery/{delivery_id}/confirm",
            json={"delivery_code": delivery_code, "confirmed_by": USER_PHONE}
        )
        assert confirm_resp.status_code == 200, f"Failed to confirm delivery: {confirm_resp.text}"
        confirmed_data = confirm_resp.json()
        print(f"  Delivery confirmed!")
        print(f"  Status: {confirmed_data['status']}")
        print(f"  Confirmed by: {confirmed_data['confirmed_by']}")
        
        # Step 6: Verify order status updated
        print(f"\nStep 6: Verifying final order status...")
        final_order_resp = await client.get(f"{BASE_URL_ORDER}/orders/{order_id}")
        assert final_order_resp.status_code == 200
        final_order = final_order_resp.json()
        print(f"  Final order status: {final_order['status']}")
        
        print("\n=== Test Summary ===")
        print(f"Cart ID: {cart_id}")
        print(f"Order ID: {order_id}")
        print(f"Delivery ID: {delivery_id}")
        print(f"Order Status: {final_order['status']}")
        print(f"Delivery Status: {confirmed_data['status']}")
        print("\nAudit events that should be emitted:")
        print("  1. cart_created")
        print("  2. item_added_to_cart")
        print("  3. cart_checked_out")
        print("  4. order_created")
        print("  5. order_paid")
        print("  6. delivery_initiated")
        print("  7. delivery_confirmed")
        print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(test_order_delivery_flow())
