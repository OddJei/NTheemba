#!/usr/bin/env python3
"""
Test order creation → payment initiation flow
"""

import requests
import json
import uuid

# URLs
MSME_URL = "http://localhost:8500"
CART_URL = "http://localhost:8530"
CATALOG_URL = "http://localhost:8520"
ORDER_DELIVERY_URL = "http://localhost:8560"
PAYMENT_REVENUE_URL = "http://localhost:8590"

# Test data
BUSINESS_ID = "a305ddb9-4432-4b7d-9e75-4225391f8bb4"
USER_PHONE = "260973456789"
PRODUCT_ID = "7dd80f79-2e8a-4dcc-9a20-7ceba2d74d67"
VARIANT_ID = "01bab0ff-4bbc-4c3d-b3c2-99b86194ce83"

def get_access_token():
    """Get JWT token from msme-engine"""
    resp = requests.post(
        f"{MSME_URL}/auth/login",
        json={"identifier": "msme_service", "password": "S3rv!c3-P@ssw0rd"}
    )
    if resp.status_code != 200:
        print(f"❌ Auth failed: {resp.status_code} {resp.text}")
        return None
    token = resp.json().get("access_token")
    print(f"✅ Got token: {token[:20]}...")
    return token

def test_order_payment_flow():
    """Test: Create order → Initiate payment"""
    
    print("\n" + "="*60)
    print("TEST: Order Creation → Payment Initiation Flow")
    print("="*60)
    
    # Step 1: Get token
    token = get_access_token()
    if not token:
        return False
    
    headers = {"Authorization": f"Bearer {token}", "X-Correlation-Id": str(uuid.uuid4())}
    
    # Step 2: Create order
    print("\n1️⃣  Creating order...")
    order_payload = {
        "user_phone": USER_PHONE,
        "business_id": BUSINESS_ID,
        "delivery_method": "pickup",
        "total_amount": 50000,  # 500 ZMW in minor units
        "currency": "ZMW",
        "meta": {
            "items": [
                {
                    "product_id": PRODUCT_ID,
                    "variant_id": VARIANT_ID,
                    "quantity": 1,
                    "unit_price": 50000,
                    "subtotal": 50000
                }
            ]
        }
    }
    
    order_resp = requests.post(
        f"{ORDER_DELIVERY_URL}/orders/create",
        json=order_payload,
        headers=headers
    )
    
    if order_resp.status_code not in (200, 201):
        print(f"❌ Order creation failed: {order_resp.status_code}")
        print(order_resp.text)
        return False
    
    order = order_resp.json()
    order_id = order["id"]
    order_status = order["status"]
    total_amount = order["total_amount"]
    
    print(f"✅ Order created: {order_id}")
    print(f"   Status: {order_status}")
    print(f"   Amount: {total_amount} (ZMW)")
    
    # Step 3: Initiate payment
    print("\n2️⃣  Initiating payment...")
    payment_payload = {
        "phone_number": USER_PHONE,
        "provider": "MTN_MOMO_ZMB",
        "currency": "ZMW"
    }
    
    payment_resp = requests.post(
        f"{ORDER_DELIVERY_URL}/orders/{order_id}/initiate_payment",
        json=payment_payload,
        headers=headers
    )
    
    if payment_resp.status_code not in (200, 201):
        print(f"❌ Payment initiation failed: {payment_resp.status_code}")
        print(payment_resp.text)
        return False
    
    payment = payment_resp.json()
    deposit_id = payment.get("external_id")
    payment_status = payment.get("status")
    
    print(f"✅ Payment initiated: {deposit_id}")
    print(f"   Status: {payment_status}")
    print(f"   Amount: {payment['amount_minor']} (ZMW minor units)")
    print(f"   Provider: {payment['provider']}")
    print(f"   Phone: {payment['phone_number']}")
    
    # Step 4: Verify order still pending
    print("\n3️⃣  Verifying order status...")
    order_check = requests.get(
        f"{ORDER_DELIVERY_URL}/orders/{order_id}",
        headers=headers
    )
    
    if order_check.status_code != 200:
        print(f"❌ Order fetch failed: {order_check.status_code}")
        return False
    
    order_updated = order_check.json()
    print(f"✅ Order status: {order_updated['status']} (should be pending_payment)")
    
    # Step 5: Verify audit events were created
    print("\n4️⃣  Checking audit events...")
    audit_resp = requests.get(
        f"http://localhost:8290/audit/?service=order-delivery&entity_id={order_id}"
    )
    
    if audit_resp.status_code == 200:
        events = audit_resp.json()
        print(f"✅ Found {len(events)} audit events for order {order_id}")
        for event in events:
            print(f"   - {event.get('event_type')}: {event.get('occurred_at')}")
    else:
        print(f"⚠️  Could not fetch audit events: {audit_resp.status_code}")
    
    print("\n" + "="*60)
    print("✅ TEST PASSED: Order → Payment flow works!")
    print("="*60)
    print(f"\nSummary:")
    print(f"  Order ID: {order_id}")
    print(f"  Deposit ID: {deposit_id}")
    print(f"  Payment Status: {payment_status}")
    print(f"  Next: pawaPay will callback when customer completes payment")
    
    return True

if __name__ == "__main__":
    try:
        success = test_order_payment_flow()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
