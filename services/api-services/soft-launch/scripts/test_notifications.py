#!/usr/bin/env python3
"""Test 5 businesses with payments and check notifications."""

import httpx
import json
import uuid
import time
import os

base_msme = 'http://localhost:8500'
base_payment = 'http://localhost:8590'

def run_test():
    """Register 5 businesses with payments."""
    print("\n" + "="*70)
    print("NOTIFICATION SERVICE TEST - 5 BUSINESSES")
    print("="*70)
    
    results = []
    
    for i in range(5):
        try:
            suffix = uuid.uuid4().hex[:8]
            username = f'user_{i}_{suffix}'
            
            print(f"\nBusiness #{i+1}: {username}")
            
            # Register user
            print("  [1] Register user...", end=" ")
            user_resp = httpx.post(f'{base_msme}/auth/register', 
                json={'username': username, 'password': 'Test123!'}, timeout=10)
            user_data = user_resp.json()
            user_id = user_data.get('id') or user_data.get('user_id')
            print(f"OK: {user_id}")
            
            # Register business
            print("  [2] Register business...", end=" ")
            biz_resp = httpx.post(f'{base_msme}/businesses', 
                json={'name': f'Business_{i}_{suffix}', 'owner_user_id': user_id}, 
                timeout=10)
            biz_data = biz_resp.json()
            business_id = biz_data.get('id') or biz_data.get('business_id')
            print(f"OK: {business_id}")
            
            # Login
            print("  [3] Login...", end=" ")
            login_resp = httpx.post(f'{base_msme}/auth/login',
                json={'username': username, 'password': 'Test123!'},
                timeout=10)
            auth_data = login_resp.json()
            token = auth_data.get('access_token')
            print("OK")
            
            # Subscribe and pay
            print("  [4] Subscribe and pay...", end=" ")
            sub_resp = httpx.post(f'{base_msme}/subscriptions/subscribe_and_pay',
                json={'plan': 'paid'},
                headers={'Authorization': f'Bearer {token}'},
                timeout=10)
            sub_data = sub_resp.json()
            deposit_id = sub_data.get('deposit_id')
            print(f"OK: {deposit_id}")
            
            # Simulate callback
            print("  [5] Simulate payment callback...", end=" ")
            httpx.post(f'{base_payment}/callbacks/pawapay/deposits',
                json={'deposit_id': deposit_id, 'status': 'COMPLETED', 'amount': 100, 'currency': 'ZWL'},
                timeout=10)
            print("OK")
            
            # Flush outbox
            print("  [6] Flush outbox...", end=" ")
            httpx.post(f'{base_payment}/jobs/outbox/flush', timeout=10)
            print("OK")
            
            results.append({'num': i+1, 'user_id': user_id, 'business_id': business_id, 'status': 'success'})
            
        except Exception as e:
            print(f"FAIL: {str(e)[:50]}")
            results.append({'num': i+1, 'status': 'failed'})
    
    # Summary
    success_count = sum(1 for r in results if r.get('status') == 'success')
    print("\n" + "="*70)
    print("REGISTRATION SUMMARY")
    print("="*70)
    print(f"Successful: {success_count}/5")
    for r in results:
        status = "OK" if r.get('status') == 'success' else "FAIL"
        print(f"  [{status}] Business #{r['num']}")
    
    # Wait for workers
    print(f"\nWaiting 15 seconds for workers...")
    for j in range(15):
        print(".", end="", flush=True)
        time.sleep(1)
    print("\n")
    
    # Check notifications
    check_notifications()
    check_databases()

def check_notifications():
    """Check notification queue."""
    print("\n" + "="*70)
    print("NOTIFICATION SERVICE")
    print("="*70)
    
    notif_file = './services/notification/dev_notifications.json'
    
    if os.path.exists(notif_file):
        with open(notif_file, 'r') as f:
            data = json.load(f)
            notifs = data.get('notifications', [])
            print(f"Total notifications queued: {len(notifs)}")
            
            if notifs:
                print("\nLatest notifications:")
                for n in notifs[-10:]:
                    ch = n.get('channel', 'unknown')
                    st = n.get('status', 'unknown')
                    uid = n.get('user_id', 'N/A')
                    print(f"  - {ch:10} | {st:15} | {uid[:20]}")
    else:
        print(f"Notification file not found: {notif_file}")
        print("(No notifications have been queued)")

def check_databases():
    """Check database events."""
    print("\n" + "="*70)
    print("DATABASE EVENTS")
    print("="*70)
    
    print("\n1. MSME Engine Events:")
    try:
        resp = httpx.get('http://localhost:8290/audit/?service=msme-engine&limit=100', timeout=10)
        if resp.status_code == 200:
            events = resp.json()
            event_types = {}
            for e in events:
                et = e.get('event_type', 'unknown')
                event_types[et] = event_types.get(et, 0) + 1
            
            print(f"   Total events: {len(events)}")
            for et, count in sorted(event_types.items()):
                print(f"     {et}: {count}")
        else:
            print(f"   Failed: {resp.status_code}")
    except Exception as e:
        print(f"   Error: {str(e)[:50]}")
    
    print("\n2. Payment Revenue Outbox:")
    try:
        import subprocess
        result = subprocess.run([
            'docker', 'exec', '-i', 'soft-launch-postgres-1',
            'psql', '-U', 'postgres', '-d', 'ntheemba', '-t', '-A', '-c',
            "SELECT COUNT(*) FROM payment_revenue.outbox WHERE status='sent';"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            count = result.stdout.strip()
            print(f"   Events sent: {count}")
        else:
            print(f"   Error: {result.stderr[:50]}")
    except Exception as e:
        print(f"   Error: {str(e)[:50]}")

if __name__ == '__main__':
    run_test()
