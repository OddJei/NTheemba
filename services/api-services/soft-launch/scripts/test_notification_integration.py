#!/usr/bin/env python3
"""
Test script to register businesses, subscribe, pay, and verify notifications
"""
import httpx
import uuid
import time
from datetime import datetime

BASE_MSME = 'http://localhost:8500'
BASE_PAYMENT = 'http://localhost:8590'
BASE_NOTIFICATION = 'http://localhost:8570'

def register_and_subscribe_business(index):
    """Register a business, subscribe, and return business details"""
    suffix = uuid.uuid4().hex[:8]
    
    # 1. Register user
    user_data = {
        "email": f"testuser{suffix}@example.com",
        "password": "TestPass123!",
        "full_name": f"Test User {suffix}"
    }
    
    print(f"\n[Business {index}] Registering user...")
    reg_resp = httpx.post(f'{BASE_MSME}/auth/register', json=user_data, timeout=15)
    if reg_resp.status_code != 201:
        print(f"  ❌ User registration failed: {reg_resp.status_code}")
        return None
    
    user_id = reg_resp.json()['user_id']
    print(f"  ✓ User registered: {user_id}")
    
    # 2. Login
    login_resp = httpx.post(f'{BASE_MSME}/auth/login', json={
        "email": user_data["email"],
        "password": user_data["password"]
    }, timeout=15)
    
    if login_resp.status_code != 200:
        print(f"  ❌ Login failed: {login_resp.status_code}")
        return None
    
    token = login_resp.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    print(f"  ✓ Logged in")
    
    # 3. Register business
    biz_data = {
        "name": f"Test Business {suffix}",
        "description": f"Test business for notification integration test",
        "category": "retail"
    }
    
    print(f"[Business {index}] Registering business...")
    biz_resp = httpx.post(f'{BASE_MSME}/businesses', json=biz_data, headers=headers, timeout=15)
    if biz_resp.status_code != 201:
        print(f"  ❌ Business registration failed: {biz_resp.status_code}")
        return None
    
    business_id = biz_resp.json()['id']
    print(f"  ✓ Business registered: {business_id}")
    
    # 4. Subscribe and pay
    sub_data = {
        "plan": "paid",
        "currency": "ZMW",
        "amount": 100,
        "payment_method": "pawapay"
    }
    
    print(f"[Business {index}] Initiating subscribe_and_pay...")
    sub_resp = httpx.post(
        f'{BASE_MSME}/businesses/{business_id}/subscribe_and_pay',
        json=sub_data,
        headers=headers,
        timeout=15
    )
    
    if sub_resp.status_code != 201:
        print(f"  ❌ Subscribe and pay failed: {sub_resp.status_code}")
        print(f"  Response: {sub_resp.text}")
        return None
    
    sub_result = sub_resp.json()
    deposit_id = sub_result.get('deposit_id')
    print(f"  ✓ Subscription initiated, deposit_id: {deposit_id}")
    
    # 5. Simulate pawaPay callback
    print(f"[Business {index}] Simulating pawaPay callback...")
    callback_data = {
        "depositId": deposit_id,
        "status": "COMPLETED",
        "requestedAmount": "100.00",
        "depositedAmount": "100.00",
        "currency": "ZMW"
    }
    
    callback_resp = httpx.post(
        f'{BASE_PAYMENT}/callbacks/pawapay/deposits',
        json=callback_data,
        timeout=15
    )
    
    if callback_resp.status_code not in [200, 201]:
        print(f"  ❌ Callback failed: {callback_resp.status_code}")
        return None
    
    print(f"  ✓ Callback completed")
    
    # 6. Flush outbox
    print(f"[Business {index}] Flushing outbox...")
    flush_resp = httpx.post(f'{BASE_PAYMENT}/jobs/outbox/flush', timeout=15)
    if flush_resp.status_code == 200:
        print(f"  ✓ Outbox flushed")
    else:
        print(f"  ⚠ Outbox flush returned: {flush_resp.status_code}")
    
    return {
        'index': index,
        'user_id': user_id,
        'business_id': business_id,
        'deposit_id': deposit_id,
        'email': user_data['email']
    }

def query_notifications_for_business(business_id, user_id):
    """Query notification service for notifications"""
    print(f"\n[Query] Checking notifications for business {business_id}...")
    
    try:
        # Try to get notifications by business (if endpoint supports it)
        resp = httpx.get(f'{BASE_NOTIFICATION}/notification/user/{user_id}', timeout=15)
        if resp.status_code == 200:
            notifications = resp.json()
            print(f"  ✓ Found {len(notifications)} notifications for user {user_id}")
            for notif in notifications:
                print(f"    - {notif['id']}: {notif['channel']} - {notif['status']}")
            return notifications
        else:
            print(f"  ⚠ Query returned: {resp.status_code}")
            return []
    except Exception as e:
        print(f"  ❌ Error querying notifications: {e}")
        return []

def check_notification_storage():
    """Check notification service storage file"""
    import json
    import os
    
    # Default notification storage path
    storage_paths = [
        'c:/Users/SMART PC/Documents/NTheemba/services/api-services/soft-launch/services/notification/dev_notifications.json',
        './services/notification/dev_notifications.json',
        './dev_notifications.json'
    ]
    
    print("\n[Storage] Checking notification storage files...")
    for path in storage_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                notifications = data.get('notifications', [])
                print(f"  ✓ Found storage at: {path}")
                print(f"  ✓ Total notifications: {len(notifications)}")
                
                # Show recent notifications
                recent = sorted(notifications, key=lambda x: x.get('created_at', ''), reverse=True)[:10]
                print(f"\n  Recent notifications:")
                for n in recent:
                    print(f"    - {n['id']}: {n['channel']} → {n['status']} (created: {n['created_at']})")
                
                # Count by status
                from collections import Counter
                status_counts = Counter(n['status'] for n in notifications)
                print(f"\n  Status breakdown:")
                for status, count in status_counts.items():
                    print(f"    {status}: {count}")
                
                return notifications
            except Exception as e:
                print(f"  ❌ Error reading {path}: {e}")
    
    print(f"  ⚠ No notification storage found")
    return []

def main():
    print("=" * 70)
    print("NOTIFICATION INTEGRATION TEST")
    print("=" * 70)
    print(f"Started at: {datetime.now()}")
    print()
    
    # Register 5 businesses
    businesses = []
    for i in range(1, 6):
        result = register_and_subscribe_business(i)
        if result:
            businesses.append(result)
        time.sleep(1)  # Brief pause between registrations
    
    print("\n" + "=" * 70)
    print(f"Successfully registered {len(businesses)} businesses")
    print("=" * 70)
    
    # Wait a bit for events to propagate
    print("\nWaiting 5 seconds for events to propagate...")
    time.sleep(5)
    
    # Query notifications for each business
    print("\n" + "=" * 70)
    print("QUERYING NOTIFICATION SERVICE")
    print("=" * 70)
    
    all_notifications = []
    for biz in businesses:
        notifs = query_notifications_for_business(biz['business_id'], biz['user_id'])
        all_notifications.extend(notifs)
    
    # Check storage file
    print("\n" + "=" * 70)
    print("CHECKING NOTIFICATION STORAGE")
    print("=" * 70)
    storage_notifs = check_notification_storage()
    
    # Query MSME events
    print("\n" + "=" * 70)
    print("QUERYING MSME EVENTS")
    print("=" * 70)
    
    try:
        # Query via audit service if available
        audit_resp = httpx.get(
            f'http://localhost:8290/audit/?service=msme-engine&limit=50',
            timeout=15
        )
        if audit_resp.status_code == 200:
            events = audit_resp.json()
            print(f"  ✓ Found {len(events)} MSME events via audit service")
            
            # Count by event type
            from collections import Counter
            event_counts = Counter(e.get('event_type') for e in events)
            print(f"\n  Event type breakdown:")
            for event_type, count in event_counts.most_common():
                print(f"    {event_type}: {count}")
        else:
            print(f"  ⚠ Audit query returned: {audit_resp.status_code}")
    except Exception as e:
        print(f"  ❌ Error querying audit: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Businesses registered: {len(businesses)}")
    print(f"Notifications via API: {len(all_notifications)}")
    print(f"Notifications in storage: {len(storage_notifs)}")
    
    print("\nBusiness Details:")
    for biz in businesses:
        print(f"  {biz['index']}. Business: {biz['business_id']}")
        print(f"     User: {biz['user_id']}")
        print(f"     Email: {biz['email']}")
        print(f"     Deposit: {biz['deposit_id']}")
    
    print(f"\nCompleted at: {datetime.now()}")
    print("=" * 70)

if __name__ == '__main__':
    main()
