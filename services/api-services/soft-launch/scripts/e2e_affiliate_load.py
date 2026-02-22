import argparse
import concurrent.futures
import requests
import time
import uuid
import statistics

MSME = "http://localhost:8500"
AFF = "http://localhost:8510"


def create_user(session, username, email, phone, password="pass123"):
    payload = {"username": username, "email": email, "phone": phone, "password": password}
    r = session.post(f"{MSME}/auth/register", json=payload, timeout=5)
    if r.status_code == 409:
        login = session.post(f"{MSME}/auth/login", json={"identifier": username, "password": password}, timeout=5)
        login.raise_for_status()
        tokens = login.json()
        headers = {"Authorization": f"Bearer {tokens.get('access_token')}"}
        me = session.get(f"{MSME}/auth/me", headers=headers, timeout=5)
        me.raise_for_status()
        return me.json()
    r.raise_for_status()
    return r.json()


def create_business_for_user(session, user_id, name=None):
    data = {"owner_user_id": user_id, "name": name or f"Biz-{user_id[:6]}"}
    r = session.post(f"{MSME}/business/register", json=data, timeout=5)
    r.raise_for_status()
    return r.json().get("business", {}).get("id")


def create_affiliate(session, name, phone=None):
    payload = {"name": name, "phone": phone}
    r = session.post(f"{AFF}/affiliates", json=payload, timeout=5)
    r.raise_for_status()
    return r.json().get("id")


def post_event(affiliate_id, business_id, timeout=10):
    payload = {
        "event_id": str(uuid.uuid4()),
        "correlation_id": str(uuid.uuid4()),
        "order_id": f"order-{uuid.uuid4()}",
        "affiliate_id": affiliate_id,
        "business_id": business_id,
        "amount_zmw": 100.0,
        "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    start = time.time()
    try:
        r = requests.post(f"{AFF}/events/order/delivered", json=payload, timeout=timeout)
        latency = time.time() - start
        return r.status_code, r.text, latency
    except Exception as exc:
        return None, str(exc), time.time() - start


def run_load_per_affiliate(affiliates, business_id, events_per_affiliate, concurrency):
    summary = {}
    for aid in affiliates:
        results = []
        failures = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = [ex.submit(post_event, aid, business_id) for _ in range(events_per_affiliate)]
            for fut in concurrent.futures.as_completed(futures):
                status, text, latency = fut.result()
                if status and 200 <= status < 300:
                    results.append(latency)
                else:
                    failures += 1
        total = events_per_affiliate
        successes = len(results)
        mean = statistics.mean(results) if results else 0.0
        p95 = statistics.quantiles(results, n=100)[94] if results and len(results) >= 2 else (max(results) if results else 0.0)
        summary[aid] = {"sent": total, "successes": successes, "failures": failures, "mean": mean, "p95": p95}
        print(f"Affiliate {aid}: sent={total} successes={successes} failures={failures} mean_latency={mean:.3f}s p95={p95:.3f}s")
    return summary


def get_pool_standings():
    r = requests.get(f"{AFF}/pool/standings", timeout=10)
    r.raise_for_status()
    return r.json()


def parse_args():
    p = argparse.ArgumentParser(description="Parallel affiliate event load tester")
    p.add_argument("--affiliates", type=int, default=3)
    p.add_argument("--events", type=int, default=200)
    p.add_argument("--concurrency", type=int, default=50)
    return p.parse_args()


if __name__ == '__main__':
    args = parse_args()
    session = requests.Session()

    # create users and a business (owner = user0)
    users = []
    for i in range(args.affiliates):
        u = create_user(session, f"loaduser{i+1}", f"loaduser{i+1}@example.com", f"2609713000{i+1}")
        users.append(u)
        print("Created user:", u.get("id"))

    biz_id = create_business_for_user(session, users[0].get("id"), name="LoadTestBiz")
    print("Created business:", biz_id)

    affiliates = []
    for i in range(args.affiliates):
        aid = create_affiliate(session, f"load-affiliate{i+1}", phone=f"2609714000{i+1}")
        affiliates.append(aid)
        print("Created affiliate:", aid)

    print(f"Running load: affiliates={len(affiliates)} events_per_affiliate={args.events} concurrency={args.concurrency}")
    start_tot = time.time()
    summary = run_load_per_affiliate(affiliates, biz_id, args.events, args.concurrency)
    total_time = time.time() - start_tot
    print("Total time:", f"{total_time:.2f}s")

    print("Pool standings summary:")
    print(get_pool_standings())
