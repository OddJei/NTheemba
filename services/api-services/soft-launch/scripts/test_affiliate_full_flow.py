#!/usr/bin/env python3
"""
Integration test: full affiliate lifecycle

Steps:
 - (Try) create affiliate role / user in MSME engine (best-effort)
 - create affiliate in affiliate-engine
 - simulate session creations and order/delivered events
 - fetch affiliate dashboard / metrics
 - attempt to trigger pool allocation / payout via admin endpoints (best-effort)

Settings via ENV:
 - MSME_BASE_URL (default http://127.0.0.1:8500)
 - AFFILIATE_BASE_URL (default http://127.0.0.1:8510)

This script is tolerant of missing endpoints and reports what succeeds.
"""
import os
import time
import uuid
import requests


MSME_BASE = os.getenv("MSME_BASE_URL", "http://127.0.0.1:8500").rstrip("/")
AFF_BASE = os.getenv("AFFILIATE_ENGINE_BASE_URL", os.getenv("AFFILIATE_BASE_URL", "http://127.0.0.1:8510")).rstrip("/")
INTERNAL_SECRET = os.getenv("OUTBOX_INTERNAL_SECRET", os.getenv("X_INTERNAL_SECRET", ""))


def try_post(url, json=None, headers=None, timeout=6):
    try:
        r = requests.post(url, json=json, headers=headers or {}, timeout=timeout)
        return r
    except Exception as e:
        print(f"   [ERR] POST {url} -> {e}")
        return None


def try_get(url, headers=None, timeout=6):
    try:
        r = requests.get(url, headers=headers or {}, timeout=timeout)
        return r
    except Exception as e:
        print(f"   [ERR] GET {url} -> {e}")
        return None


def create_msme_affiliate_role():
    print("[1] Creating MSME affiliate role (best-effort)")
    candidates = [
        (f"{MSME_BASE}/roles", {"name": "affiliate"}),
        (f"{MSME_BASE}/users", {"identifier": "affiliate_bot_%s" % uuid.uuid4().hex[:6], "roles": ["affiliate"]}),
    ]
    for url, payload in candidates:
        print(f"   Trying {url} ...")
        r = try_post(url, json=payload)
        if r is None:
            continue
        print(f"      -> {r.status_code} {r.text[:200]}")
        if r.status_code in (200, 201):
            print("      [OK] MSME role/user created (or already exists)")
            return True
    print("   [WARN] Could not create role/user in MSME — continuing anyway")
    return False


def create_affiliate():
    print("[2] Creating affiliate in affiliate-engine")
    payload = {
        "name": "auto-test-affiliate",
        "owner_phone": "260977000000",
        "affiliate_code": f"AUTOTEST{int(time.time())%10000}",
    }
    candidates = [
        f"{AFF_BASE}/affiliates",
        f"{AFF_BASE}/admin/affiliates",
        f"{AFF_BASE}/affiliates/create",
    ]
    for url in candidates:
        print(f"   Trying {url} ...")
        r = try_post(url, json=payload)
        if r is None:
            continue
        print(f"      -> {r.status_code} {r.text[:200]}")
        if r.status_code in (200, 201):
            try:
                j = r.json()
                aid = j.get("id") or j.get("affiliate_id") or j.get("affiliateId") or j.get("affiliate_id")
                if not aid:
                    # Some endpoints return nested object
                    if isinstance(j, dict):
                        for v in j.values():
                            if isinstance(v, dict) and (v.get("id") or v.get("affiliate_id")):
                                aid = v.get("id") or v.get("affiliate_id")
                                break
                print(f"      [OK] Affiliate created id={aid}")
                return aid or j
            except Exception:
                return r.text
    print("   [ERROR] Failed to create affiliate — aborting")
    return None


def simulate_performance(affiliate_id, business_id=None, n_sessions=3, n_sales=5):
    print("[3] Simulating sessions and sales")
    # Create sessions
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for i in range(n_sessions):
        payload = {
            "event_id": f"session-{affiliate_id}-{i}-{uuid.uuid4().hex[:6]}",
            "event_type": "session_cycle_created",
            "occurred_at": now,
            "producer": "test-harness",
            "affiliate_id": affiliate_id,
            "session_id": f"sess-{uuid.uuid4().hex[:6]}",
            "cycle_id": f"cycle-{i}",
            "cycle_state": "started",
            "user_phone": f"26097{800000+i}",
        }
        r = try_post(f"{AFF_BASE}/events/session-cycle-created", json=payload)
        print(f"   session {i} -> {getattr(r,'status_code',None)}")

    # Create sales via order/delivered events
    for i in range(n_sales):
        order_id = f"test-order-{uuid.uuid4().hex[:8]}"
        payload = {
            "event_id": f"delivered-{order_id}",
            "event_type": "order_delivered",
            "occurred_at": now,
            "correlation_id": str(uuid.uuid4()),
            "order_id": order_id,
            "business_id": business_id or "test-business-1",
            "affiliate_id": affiliate_id,
            "amount_zmw": 1000 + i * 100,  # incremental amounts
            "user_phone": f"26097{700000+i}",
            "cycle_id": f"cycle-{i}",
        }
        r = try_post(f"{AFF_BASE}/events/order/delivered", json=payload)
        print(f"   sale {i} -> {getattr(r,'status_code',None)}")


def fetch_dashboard(affiliate_id):
    print("[4] Fetching affiliate dashboard / metrics")
    candidates = [
        f"{AFF_BASE}/affiliates/{affiliate_id}/dashboard",
        f"{AFF_BASE}/affiliates/{affiliate_id}/metrics",
        f"{AFF_BASE}/affiliates/{affiliate_id}",
    ]
    for url in candidates:
        print(f"   GET {url} ...")
        r = try_get(url)
        if r is None:
            continue
        print(f"      -> {r.status_code} {r.text[:400]}")
        if r.status_code == 200:
            try:
                print("      [OK] Metrics:")
                print(r.json())
                return r.json()
            except Exception:
                return r.text
    print("   [WARN] Could not fetch dashboard/metrics")
    return None


def trigger_pool_and_payout():
    print("[5] Attempting to trigger pool allocation / payout (admin endpoints, best-effort)")
    candidates = [
        (f"{AFF_BASE}/admin/pool/close", {}),
        (f"{AFF_BASE}/admin/pool/allocate", {}),
        (f"{AFF_BASE}/pool/close", {}),
        (f"{AFF_BASE}/admin/payouts/initiate", {}),
        (f"{AFF_BASE}/admin/payouts", {"action": "initiate"}),
    ]
    for url, payload in candidates:
        print(f"   Trying {url} ...")
        r = try_post(url, json=payload)
        if r is None:
            continue
        print(f"      -> {r.status_code} {r.text[:400]}")
        if r.status_code in (200, 201):
            print("      [OK] Pool/payout endpoint accepted the request")
            return r.json() if r.headers.get("content-type","").startswith("application/json") else r.text
    print("   [WARN] No admin pool/payout endpoint accepted the request")
    return None


def main():
    print("Running affiliate full-flow integration test")
    print(f" MSME: {MSME_BASE}")
    print(f" AFFILIATE: {AFF_BASE}")

    create_msme_affiliate_role()
    aff = create_affiliate()
    if not aff:
        print("Failed to create affiliate — exiting")
        return
    # If create_affiliate returned object/dict with id
    affiliate_id = aff if isinstance(aff, str) else (aff.get("id") if isinstance(aff, dict) else None)
    if not affiliate_id:
        # sometimes API returns raw text id
        affiliate_id = str(aff)

    # Try fetching a business id from MSME to use in order events
    business_id = None
    if INTERNAL_SECRET:
        try:
            print("[INFO] Fetching MSME businesses for test")
            h = {"X-Internal-Secret": INTERNAL_SECRET}
            r = try_get(f"{MSME_BASE}/internal/businesses", headers=h)
            if r and r.status_code == 200:
                j = r.json()
                if isinstance(j, list) and len(j) > 0:
                    business_id = j[0].get("id")
                    print(f"[INFO] Using business_id={business_id} from MSME")
        except Exception as e:
            print("[WARN] Could not fetch business list:", e)

    simulate_performance(affiliate_id, business_id=business_id)
    time.sleep(1)
    fetch_dashboard(affiliate_id)
    trigger_pool_and_payout()


if __name__ == "__main__":
    main()
