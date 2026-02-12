#!/usr/bin/env python3
"""
Test the full payment callback flow:
1. Create order
2. Initiate payment 
3. Simulate pawaPay callback
4. Verify order is marked as paid
"""

import httpx
import time

MSME_URL = "http://localhost:8500"
ORDER_DELIVERY_URL = "http://localhost:8560"
PAYMENT_REVENUE_URL = "http://localhost:8590"

USERNAME = "msme_service"
PASSWORD = "S3rv!c3-P@ssw0rd"
BUSINESS_ID = "a305ddb9-4432-4b7d-9e75-4225391f8bb4"


def get_access_token():
    r = httpx.post(
        f"{MSME_URL}/auth/login",
        json={"identifier": USERNAME, "password": PASSWORD},
        timeout=5,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def create_order(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    order_payload = {
        "business_id": BUSINESS_ID,
        "user_phone": "260973456789",
        "delivery_method": "pickup",
        "total_amount": 100000,  # 1000 ZMW
        "currency": "ZMW",
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
    return order["id"]


def initiate_payment(order_id: str, token: str):
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
    print(f"  Deposit ID: {payment['external_id']}")
    print(f"  Status: {payment['status']}")
    return payment["external_id"]


def simulate_pawapay_callback(deposit_id: str):
    """Simulate pawaPay calling back with COMPLETED status."""
    callback_payload = {
        "depositId": deposit_id,
        "status": "COMPLETED",
        "amount": "1000.00",
        "currency": "ZMW",
        "country": "ZMB",
        "payer": {
            "type": "MMO",
            "accountDetails": {
                "phoneNumber": "260973456789",
                "provider": "MTN_MOMO_ZMB"
            }
        },
        "created": "2026-02-02T12:00:00Z",
        "providerTransactionId": "test-12345"
    }
    
    # pawaPay callback secret (from payment-revenue env or default)
    headers = {"X-PawaPay-Callback-Secret": "dummy"}
    
    r = httpx.post(
        f"{PAYMENT_REVENUE_URL}/callbacks/pawapay/deposits",
        json=callback_payload,
        headers=headers,
        timeout=10,
    )
    r.raise_for_status()
    print(f"\n✓ pawaPay callback simulated")
    print(f"  Response: {r.json()}")


def get_order_status(order_id: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}
    r = httpx.get(
        f"{ORDER_DELIVERY_URL}/orders/{order_id}",
        headers=headers,
        timeout=5,
    )
    r.raise_for_status()
    return r.json()


def main():
    print("=" * 60)
    print("TEST: Full Payment Callback Flow")
    print("=" * 60)
    
    try:
        print("\n[1/5] Getting access token...")
        token = get_access_token()
        print(f"✓ Token: {token[:20]}...")
        
        print("\n[2/5] Creating order...")
        order_id = create_order(token)
        
        print("\n[3/5] Initiating payment...")
        deposit_id = initiate_payment(order_id, token)
        
        print("\n[4/5] Simulating pawaPay callback...")
        simulate_pawapay_callback(deposit_id)
        
        # Wait a moment for async processing
        print("\n[5/5] Waiting 2 seconds for callback processing...")
        time.sleep(2)
        
        print("\nChecking order status...")
        order = get_order_status(order_id, token)
        print(f"  Order status: {order['status']}")
        
        print("\n" + "=" * 60)
        if order['status'] == 'paid':
            print("✅ TEST PASSED - Order marked as PAID")
        else:
            print(f"❌ TEST FAILED - Order status is {order['status']}, expected 'paid'")
        print("=" * 60)
        
    except httpx.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        if hasattr(e, "response") and e.response:
            print(f"Response: {e.response.text}")
        raise
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
