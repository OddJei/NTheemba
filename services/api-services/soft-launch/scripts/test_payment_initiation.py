#!/usr/bin/env python3
"""
Test the new order-delivery payment initiation endpoint.
Flow: Create order → Initiate payment → Verify payment started
"""

import httpx
import json
import uuid

MSME_URL = "http://localhost:8500"
ORDER_DELIVERY_URL = "http://localhost:8560"
PAYMENT_REVENUE_URL = "http://localhost:8590"

# Test credentials
USERNAME = "msme_service"
PASSWORD = "S3rv!c3-P@ssw0rd"

# Test business/product IDs from database
BUSINESS_ID = "a305ddb9-4432-4b7d-9e75-4225391f8bb4"
PRODUCT_ID = "7dd80f79-2e8a-4dcc-9a20-7ceba2d74d67"
VARIANT_ID = "01bab0ff-4bbc-4c3d-b3c2-99b86194ce83"


def get_access_token():
    """Get JWT token from msme-engine."""
    r = httpx.post(
        f"{MSME_URL}/auth/login",
        json={"identifier": USERNAME, "password": PASSWORD},
        timeout=5,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def create_order(token: str):
    """Create an order in order-delivery."""
    headers = {"Authorization": f"Bearer {token}"}
    
    order_payload = {
        "business_id": BUSINESS_ID,
        "user_phone": "260973456789",
        "user_id": None,
        "delivery_method": "pickup",
        "total_amount": 50000,  # 500 ZMW in minor units
        "currency": "ZMW",
        "metadata": {
            "items": [
                {
                    "product_id": PRODUCT_ID,
                    "variant_id": VARIANT_ID,
                    "quantity": 1,
                    "unit_price": 50000,
                }
            ]
        },
    }
    
    r = httpx.post(
        f"{ORDER_DELIVERY_URL}/orders/create",
        json=order_payload,
        headers=headers,
        timeout=5,
    )
    r.raise_for_status()
    order = r.json()
    print(f"✓ Order created: {order['id']}")
    print(f"  Status: {order['status']}")
    print(f"  Total: {order['total_amount']} {order['currency']}")
    return order["id"]


def initiate_payment(order_id: str, token: str):
    """Initiate payment for the order."""
    headers = {"Authorization": f"Bearer {token}"}
    
    payment_payload = {
        "phoneNumber": "260973456789",
        "provider": "MTN_MOMO_ZMB",
        "currency": "ZMW",
    }
    
    r = httpx.post(
        f"{ORDER_DELIVERY_URL}/orders/{order_id}/initiate_payment",
        json=payment_payload,
        headers=headers,
        timeout=10,
    )
    r.raise_for_status()
    payment = r.json()
    print(f"\n✓ Payment initiated")
    print(f"  Deposit ID: {payment.get('external_id')}")
    print(f"  Status: {payment.get('status')}")
    print(f"  Amount: {payment.get('amount_minor')} {payment.get('currency')}")
    print(f"  Provider: {payment.get('provider')}")
    return payment


def main():
    print("=" * 60)
    print("TEST: Order → Payment Initiation Flow")
    print("=" * 60)
    
    try:
        # Step 1: Get token
        print("\n[1/3] Getting access token...")
        token = get_access_token()
        print(f"✓ Token: {token[:20]}...")
        
        # Step 2: Create order
        print("\n[2/3] Creating order...")
        order_id = create_order(token)
        
        # Step 3: Initiate payment
        print("\n[3/3] Initiating payment...")
        payment = initiate_payment(order_id, token)
        
        print("\n" + "=" * 60)
        print("✅ TEST PASSED")
        print("=" * 60)
        print(f"\nOrder ID: {order_id}")
        print(f"Deposit ID: {payment.get('external_id')}")
        print(f"\nPayment status: {payment.get('status')}")
        if payment.get('status') == 'ACCEPTED':
            print("✓ Payment accepted by pawaPay (sandbox mode)")
        
    except httpx.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        if hasattr(e.response, "text"):
            print(f"Response: {e.response.text}")
        raise
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
