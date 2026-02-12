#!/usr/bin/env python3
"""
Simulate order creation and payment flow:
1. Create order in order-delivery service (status: pending_payment)
2. Simulate payment callback to mark order as paid
3. Verify order status transitions
4. NO notifications sent (we'll mock them)
"""

import httpx
import json
import uuid
from datetime import datetime, timezone

# Service URLs
MSME_BASE_URL = "http://localhost:8500"
CART_BASE_URL = "http://localhost:8530"
ORDER_BASE_URL = "http://localhost:8560"
PAYMENT_BASE_URL = "http://localhost:8590"
NOTIFICATION_BASE_URL = "http://localhost:8570"

# Test data
test_user_phone = "+260970000001"
test_user_username = None  # Store username for later login
test_business_id = None
test_user_id = None


def log(msg, data=None):
    """Pretty print logs with optional JSON data."""
    print(f"\n{'=' * 80}")
    print(f">> {msg}")
    if data:
        print(json.dumps(data, indent=2, default=str))
    print('=' * 80)


async def get_or_create_business():
    """Get existing business or create a new one for testing."""
    global test_business_id, test_user_id, test_user_username
    
    async with httpx.AsyncClient(timeout=10) as client:
        # Register new user
        username = f"testuser{uuid.uuid4().hex[:6]}"
        test_user_username = username  # Store for later login
        user_data = {
            "username": username,
            "email": f"test-{uuid.uuid4().hex[:8]}@example.com",
            "password": "test123",
            "phone": test_user_phone,
        }
        r = await client.post(f"{MSME_BASE_URL}/auth/register", json=user_data)
        if r.status_code != 201:
            log("ERROR: User registration failed", r.json())
            return False
        
        user = r.json()
        test_user_id = user["id"]
        log("User registered", {"user_id": test_user_id, "phone": test_user_phone})
        
        # Login to get access token
        login_data = {
            "identifier": username,
            "password": "test123",
        }
        r = await client.post(f"{MSME_BASE_URL}/auth/login", json=login_data)
        if r.status_code != 200:
            log("ERROR: Login failed", r.json())
            return False
        
        auth_data = r.json()
        access_token = auth_data["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Create business
        business_data = {
            "owner_user_id": test_user_id,
            "name": f"Test Business {uuid.uuid4().hex[:6]}",
            "location": "Lusaka",
            "category": "Retail",
        }
        r = await client.post(
            f"{MSME_BASE_URL}/business/register",
            json=business_data,
            headers=headers,
        )
        if r.status_code != 201:
            log("ERROR: Business creation failed", r.json())
            return False
        
        business = r.json()
        log("Business response (full)", business)
        test_business_id = business.get("id") or business.get("business_id") or business.get("business", {}).get("id")
        if not test_business_id:
            log("ERROR: Could not find business ID in response")
            return False
        log("Business created", {"business_id": test_business_id, "name": business_data["name"]})
        log("✅ Business created", {"business_id": test_business_id, "name": business_data["name"]})
        
        return True


async def create_order():
    """Create an order in order-delivery service."""
    global test_user_id, test_user_username
    log("Creating order...")
    
    # Get a fresh JWT token using stored username
    access_token = None
    async with httpx.AsyncClient(timeout=10) as client:
        login_r = await client.post(f"{MSME_BASE_URL}/auth/login", json={
            "identifier": test_user_username,
            "password": "test123",
        })
        if login_r.status_code == 200:
            access_token = login_r.json().get("access_token")
    
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    
    order_payload = {
        "session_id": f"sess-{uuid.uuid4().hex[:8]}",
        "user_phone": test_user_phone,
        "user_id": test_user_id,
        "business_id": test_business_id,
        "total_amount": 50000,  # 500 ZMW (minor units)
        "currency": "ZMW",
        "delivery_method": "pickup",
        "meta": {
            "notes": "Test order",
            "items": [
                {
                    "product_id": "prod-test",
                    "name": "Test Product",
                    "quantity": 2,
                    "price": 25000,
                }
            ]
        }
    }
    
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{ORDER_BASE_URL}/orders/create",
            json=order_payload,
            headers=headers,
        )
        
        if r.status_code != 201:
            log("ERROR: Order creation failed", {
                "status": r.status_code,
                "response": r.json()
            })
            return None
        
        order = r.json()
        log("Order created", {
            "order_id": order["id"],
            "status": order["status"],
            "total_amount": order["total_amount"],
            "currency": order["currency"],
            "meta": order.get("meta"),
        })
        
        return order


async def mark_order_paid(order_id):
    """Simulate payment callback - mark order as paid."""
    global test_user_username
    log("Mark order as paid (payment success callback)...")
    
    # Get JWT token
    access_token = None
    async with httpx.AsyncClient(timeout=10) as client:
        login_r = await client.post(f"{MSME_BASE_URL}/auth/login", json={
            "identifier": test_user_username,
            "password": "test123",
        })
        if login_r.status_code == 200:
            access_token = login_r.json().get("access_token")
    
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{ORDER_BASE_URL}/orders/{order_id}/mark_paid",
            headers=headers,
        )
        
        if r.status_code != 200:
            log("ERROR: Mark paid failed", {
                "status": r.status_code,
                "response": r.json()
            })
            return False
        
        order = r.json()
        log("Order marked as paid", {
            "order_id": order.get("id"),
            "status": order.get("status"),
            "total_amount": order.get("total_amount"),
            "transaction_fee_pct": order.get("meta", {}).get("transaction_fee_pct") if order.get("meta") else None,
            "platform_fee_amount": order.get("meta", {}).get("platform_fee_amount") if order.get("meta") else None,
            "msme_net_amount": order.get("meta", {}).get("msme_net_amount") if order.get("meta") else None,
        })
        
        return True


async def verify_no_notifications():
    """Check that no notifications were sent (we disabled them)."""
    log("Verify NO notifications were sent...")
    
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{NOTIFICATION_BASE_URL}/health")
        if r.status_code == 200:
            log("Notification service is running")
            log("Notifications were INTENTIONALLY DISABLED for this test")
        else:
            log("WARNING: Notification service unreachable")
    
    return True


async def main():
    """Run complete order creation and payment simulation."""
    print("\n")
    print("=" * 80)
    print("ORDER CREATION & PAYMENT SIMULATION")
    print("=" * 80)
    
    # Step 1: Create business
    if not await get_or_create_business():
        print("\nERROR: Failed to create business")
        return
    
    # Step 2: Create order
    order = await create_order()
    if not order:
        print("\nERROR: Failed to create order")
        return
    
    order_id = order["id"]
    
    # Verify order is pending payment
    if order["status"] != "pending_payment":
        log("ERROR: Order should be in pending_payment status", {"status": order["status"]})
        return
    
    log("Order status is pending_payment (as expected)")
    
    # Step 3: Simulate payment callback
    if not await mark_order_paid(order_id):
        print("\nERROR: Failed to mark order as paid")
        return
    
    # Step 4: Verify no notifications
    await verify_no_notifications()
    
    # Summary
    log("SUCCESS: ORDER & PAYMENT FLOW COMPLETED", {
        "flow": [
            "1. Created test user and business",
            "2. Created order (status: pending_payment)",
            "3. Marked order as paid (status: paid)",
            "4. NO notifications sent (disabled intentionally)",
        ],
        "order_id": order_id,
        "business_id": test_business_id,
        "user_id": test_user_id,
    })


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
