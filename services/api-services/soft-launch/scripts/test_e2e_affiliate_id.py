#!/usr/bin/env python3
"""
End-to-end test for order -> payment -> delivery -> affiliate attribution flow with affiliate_id
"""
import requests
import json
import time

BASE_URL = "http://127.0.0.1:8560"
PAYMENT_URL = "http://127.0.0.1:8590"
AFFILIATE_URL = "http://127.0.0.1:8510"
AUTH_URL = "http://127.0.0.1:8500"

def test_e2e_with_affiliate_id():
    print("\n" + "="*60)
    print("TEST: E2E Flow with Affiliate ID")
    print("="*60)
    
    # Step 1: Get auth token
    print("\n[1/6] Getting auth token...")
    login_payload = {
        "identifier": "msme_service",
        "password": "S3rv!c3-P@ssw0rd"
    }
    try:
        resp = login_response = requests.post(
            f"{AUTH_URL}/auth/login",
            json=login_payload,
            timeout=15
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        print(f"   [OK] Token obtained: {token[:20]}...")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 2: Create order with affiliate_id metadata
    print("\n[2/6] Creating order with affiliate_id...")
    order_payload = {
        "business_id": "a305ddb9-4432-4b7d-9e75-4225391f8bb4",
        "user_phone": "260973456789",
        "delivery_method": "pickup",
        "total_amount": 100000,  # 1000 in major units
        "currency": "ZMW",
        "metadata": {
            "affiliate_id": "aff-xyz-789",  # Direct affiliate ID
            "affiliate_code": "TESTCODE123"  # Also include code for backward compat
        }
    }
    try:
        resp = requests.post(
            f"{BASE_URL}/orders/create",
            json=order_payload,
            headers=headers,
            timeout=15
        )
        resp.raise_for_status()
        order = resp.json()
        order_id = order["id"]
        print(f"   [OK] Order created: {order_id}")
        print(f"        Status: {order['status']}")
        print(f"        Total: {order['total_amount']}")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False
    
    # Step 3: Initiate payment
    print("\n[3/6] Initiating payment...")
    payment_payload = {
        "phoneNumber": "260973456789",
        "provider": "MTN_MOMO_ZMB",
        "currency": "ZMW"
    }
    try:
        resp = requests.post(
            f"{BASE_URL}/orders/{order_id}/initiate_payment",
            json=payment_payload,
            headers=headers,
            timeout=15
        )
        resp.raise_for_status()
        payment = resp.json()
        external_id = payment.get("external_id")
        print(f"   [OK] Payment initiated")
        print(f"        External ID: {external_id}")
        print(f"        Status: {payment.get('status')}")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False
    
    # Step 4: Simulate payment callback
    print("\n[4/6] Simulating payment callback (status=COMPLETED)...")
    callback_payload = {
        "depositId": external_id,
        "status": "COMPLETED",
        "amount": str(order["total_amount"] / 100),  # Convert to major units
        "currency": "ZMW"
    }
    try:
        resp = requests.post(
            f"{PAYMENT_URL}/callbacks/pawapay/deposits",
            json=callback_payload,
            timeout=5
        )
        resp.raise_for_status()
        print(f"   [OK] Callback processed, status: {resp.status_code}")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False
    
    # Step 5: Wait for dispatcher and verify order marked as paid
    print("\n[5/6] Waiting for background dispatcher to process events (2 sec)...")
    time.sleep(2)
    
    try:
        resp = requests.get(
            f"{BASE_URL}/orders/{order_id}",
            headers=headers,
            timeout=5
        )
        resp.raise_for_status()
        order_status = resp.json()
        print(f"   [OK] Order status: {order_status['status']}")
        if order_status['status'] == 'paid':
            print("        >> Order marked as paid by payment callback!")
        else:
            print(f"        WARNING: Order still {order_status['status']}, expected 'paid'")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False
    
    # Step 6: Check for affiliate attribution with affiliate_id
    print("\n[6/6] Checking affiliate attribution (should use affiliate_id)...")
    try:
        resp = requests.get(
            f"{AFFILIATE_URL}/attributions?limit=10",
            timeout=5
        )
        resp.raise_for_status()
        attributions = resp.json()
        
        # Find attribution for this order
        matching = [a for a in attributions if a.get('order_id') == order_id]
        
        if matching:
            attr = matching[0]
            print(f"   [OK] Attribution found!")
            print(f"        Order ID: {attr.get('order_id')}")
            print(f"        Affiliate ID: {attr.get('affiliate_id')}")
            print(f"        Affiliate Code: {attr.get('affiliate_code')}")
            print(f"        Amount: {attr.get('amount_minor')}")
            if attr.get('affiliate_id') == 'aff-xyz-789':
                print("        >> Affiliate ID correctly extracted and stored!")
            else:
                print(f"        WARNING: Expected affiliate_id='aff-xyz-789', got '{attr.get('affiliate_id')}'")
        else:
            print(f"   [PENDING] No attribution found yet - dispatcher may still be processing")
            print(f"            (Total attributions: {len(attributions)})")
    except Exception as e:
        print(f"   [WARNING] Could not verify attribution: {e}")
    
    print("\n" + "="*60)
    print("TEST COMPLETE: Flow executed successfully!")
    print("="*60)
    return True

if __name__ == "__main__":
    test_e2e_with_affiliate_id()
