#!/usr/bin/env python3
"""
End-to-end payment callback simulation:

1. Register user → register business → login
2. Call subscribe_and_pay (initiate deposit at payment-revenue)
3. Simulate pawaPay callback (COMPLETED) → payment-revenue
4. Trigger outbox dispatch → msme-engine /events/payment_success
5. Verify audit events and subscription activation
"""
import time
import uuid
import json
import httpx


def main() -> None:
    base_msme = "http://localhost:8500"
    base_payment = "http://localhost:8590"
    base_audit = "http://localhost:8290"

    suffix = uuid.uuid4().hex[:8]
    sandbox_msisdn = "260973456789"  # COMPLETED in pawaPay sandbox

    print("=" * 70)
    print("PHASE 1: Register user → business → login")
    print("=" * 70)

    # Register user
    user = {
        "username": f"testowner_{suffix}",
        "email": f"owner_{suffix}@test.com",
        "phone": sandbox_msisdn,
        "password": "Test123!",
    }
    r = httpx.post(f"{base_msme}/auth/register", json=user, timeout=15)
    print(f"[1.1] POST /auth/register: {r.status_code}")
    r.raise_for_status()
    user_id = r.json()["id"]

    # Register business
    biz = {
        "name": f"Test MSME {suffix}",
        "owner_user_id": user_id,
        "location": "Lusaka",
        "category": "retail",
        "subscription_plan": "free",
    }
    r = httpx.post(f"{base_msme}/business/register", json=biz, timeout=15)
    print(f"[1.2] POST /business/register: {r.status_code}")
    r.raise_for_status()
    business_id = r.json()["business"]["id"]
    print(f"     business_id: {business_id}")

    # Login
    login = {"identifier": user["email"], "password": user["password"]}
    r = httpx.post(f"{base_msme}/auth/login", json=login, timeout=15)
    print(f"[1.3] POST /auth/login: {r.status_code}")
    r.raise_for_status()
    token = r.json()["access_token"]

    print()
    print("=" * 70)
    print("PHASE 2: Initiate payment (subscribe_and_pay)")
    print("=" * 70)

    correlation_id = f"callback-test-{suffix}"
    sub = {
        "plan": "paid",
        "amount_minor": 5000,
        "phone_number": sandbox_msisdn,
        "provider": "MTN_MOMO_ZMB",
        "currency": "ZMW",
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Correlation-Id": correlation_id,
    }

    r = httpx.post(
        f"{base_msme}/business/{business_id}/subscribe_and_pay",
        json=sub,
        headers=headers,
        timeout=15,
    )
    print(f"[2.1] POST /business/{{id}}/subscribe_and_pay: {r.status_code}")
    r.raise_for_status()

    resp = r.json()
    subscription_id = resp["subscription"]["id"]
    subscription_status_before = resp["subscription"]["status"]
    print(f"     subscription_id: {subscription_id}")
    print(f"     subscription.status: {subscription_status_before}")

    # Extract depositId from payment response
    pr = resp.get("payment_request", {})
    pr_resp = pr.get("payment_revenue_response", {})
    external_id = pr_resp.get("external_id")
    print(f"     payment_revenue_response.external_id (depositId): {external_id}")

    if not external_id:
        print("[ERROR] No external_id in payment response!")
        return

    print()
    print("=" * 70)
    print("PHASE 3: Simulate pawaPay callback (COMPLETED)")
    print("=" * 70)

    # Build callback payload matching pawaPay format
    pawapay_callback = {
        "depositId": external_id,
        "status": "COMPLETED",
        "amount": "50.00",  # 5000 minor = 50.00 major
        "currency": "ZMW",
        "country": "ZMB",
        "created": "2026-01-31T10:02:55Z",
        "providerTransactionId": str(uuid.uuid4()),
        "payer": {
            "type": "MMO",
            "accountDetails": {
                "phoneNumber": sandbox_msisdn,
                "provider": "MTN_MOMO_ZMB",
            },
        },
        "customerMessage": "DEMO",
    }

    # For sandbox, the callback secret is typically "test-secret" or empty;
    # adjust based on your docker-compose env
    callback_headers = {
        "X-Correlation-Id": correlation_id,
        "X-PawaPay-Secret": "test-secret",  # Adjust if needed
    }

    r = httpx.post(
        f"{base_payment}/callbacks/pawapay/deposits",
        json=pawapay_callback,
        headers=callback_headers,
        timeout=15,
    )
    print(f"[3.1] POST /callbacks/pawapay/deposits: {r.status_code}")
    print(f"      Response: {r.text[:500]}")

    if r.status_code != 200:
        print(f"[WARNING] Callback returned {r.status_code}, continuing anyway...")

    print()
    print("=" * 70)
    print("PHASE 4: Check outbox and dispatch to msme-engine")
    print("=" * 70)

    # Give the callback handler a moment to persist outbox
    time.sleep(0.5)

    # Trigger outbox flush explicitly (requires Bearer token)
    r = httpx.get(f"{base_payment}/health", timeout=5)
    print(f"[4.1] payment-revenue health: {r.status_code}")

    flush_headers = {
        "Authorization": f"Bearer {token}",
        "X-Correlation-Id": correlation_id,
    }
    r = httpx.post(f"{base_payment}/jobs/outbox/flush", headers=flush_headers, timeout=15)
    print(f"[4.2] POST /jobs/outbox/flush: {r.status_code}")
    if r.status_code != 200:
        print(f"      Response: {r.text[:500]}")

    # Give the outbox a moment to deliver
    time.sleep(2)

    print()
    print("=" * 70)
    print("PHASE 5: Verify MSME subscription activation")
    print("=" * 70)

    # Query the subscription to check if it's now ACTIVE
    r = httpx.get(
        f"{base_msme}/business/{business_id}/subscription",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    print(f"[5.1] GET /business/{{id}}/subscription: {r.status_code}")
    if r.status_code == 200:
        sub_data = r.json()
        subscription_status_after = sub_data.get("status")
        print(f"     subscription.status: {subscription_status_after}")
        if subscription_status_after == "active":
            print("     ✓ Subscription is now ACTIVE!")
        else:
            print(f"     ! Subscription is still {subscription_status_after}")
    else:
        print(f"     [ERROR] Could not fetch subscription: {r.text[:200]}")

    print()
    print("=" * 70)
    print("PHASE 6: Verify audit events")
    print("=" * 70)

    # Query audit events for this business
    r = httpx.get(
        f"{base_audit}/audit/?service=msme-engine&entity_id={business_id}",
        timeout=15,
    )
    print(f"[6.1] GET /audit/?service=msme-engine&entity_id={{business_id}}: {r.status_code}")
    if r.status_code == 200:
        audit_data = r.json()
        items = audit_data.get("items", [])
        print(f"     Total events: {len(items)}")
        
        # Show latest events
        for item in items[:5]:
            event_type = item.get("event_type")
            occurred_at = item.get("occurred_at")
            print(f"       - {event_type} @ {occurred_at}")
        
        # Check for payment_success event
        has_payment_success = any(item.get("event_type") == "payment_success" for item in items)
        if has_payment_success:
            print("     ✓ payment_success event found!")
        else:
            print("     ! payment_success event NOT found (may still be processing)")
    else:
        print(f"     [ERROR] Could not fetch audit events: {r.text[:200]}")

    print()
    print("=" * 70)
    print("PHASE 7: Verify notifications")
    print("=" * 70)

    # Try to fetch in-app notifications (if exposed)
    r = httpx.get(
        f"{base_msme}/notifications?user_id={user_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if r.status_code == 200:
        print(f"[7.1] GET /notifications: {r.status_code}")
        notifs = r.json().get("items", [])
        if notifs:
            print(f"     Notifications: {len(notifs)}")
            for n in notifs[:3]:
                print(f"       - {n.get('template')}: {n.get('payload', {}).get('message', '')}")
        if any("subscription_payment_success" in str(n.get('template', '')) for n in notifs):
            print("     ✓ Subscription payment success notification found!")
        else:
            print("     ! Payment success notification NOT found")
    else:
        print(f"[7.1] GET /notifications: {r.status_code} (notifications endpoint may not be exposed)")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Subscription ID: {subscription_id}")
    print(f"Business ID: {business_id}")
    print(f"Deposit ID: {external_id}")
    print(f"Correlation ID: {correlation_id}")
    print()
    print("Expected outcomes:")
    print("  1. Subscription status changed from 'pending_payment' to 'active'")
    print("  2. Audit events include 'payment_success' event")
    print("  3. User received 'subscription_payment_success' notification")
    print()


if __name__ == "__main__":
    main()
