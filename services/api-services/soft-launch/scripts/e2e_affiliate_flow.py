import requests
import time
import uuid
import statistics

MSME = "http://localhost:8500"
AFF = "http://localhost:8510"

session = requests.Session()


def create_user(username, email, phone, password="pass123", role="default"):
    payload = {"username": username, "email": email, "phone": phone, "password": password, "role": role}
    r = session.post(f"{MSME}/auth/register", json=payload, timeout=5)
    if r.status_code == 409:
        # user exists: try to login and fetch current user
        login = session.post(f"{MSME}/auth/login", json={"identifier": username, "password": password}, timeout=5)
        login.raise_for_status()
        tokens = login.json()
        headers = {"Authorization": f"Bearer {tokens.get('access_token')}"}
        me = session.get(f"{MSME}/auth/me", headers=headers, timeout=5)
        me.raise_for_status()
        return me.json()
    r.raise_for_status()
    return r.json()


def create_business_for_user(user_id, name=None):
    data = {"owner_user_id": user_id, "name": name or f"Biz-{user_id[:6]}"}
    r = session.post(f"{MSME}/business/register", json=data, timeout=5)
    r.raise_for_status()
    return r.json().get("business", {}).get("id")


def create_affiliate(name, phone=None):
    payload = {"name": name, "phone": phone}
    r = session.post(f"{AFF}/affiliates", json=payload, timeout=5)
    r.raise_for_status()
    return r.json().get("id")


def send_order_delivered(affiliate_id=None, business_id=None, count=1):
    latencies = []
    successes = 0
    for i in range(count):
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
        r = session.post(f"{AFF}/events/order/delivered", json=payload, timeout=10)
        latency = time.time() - start
        latencies.append(latency)
        if 200 <= r.status_code < 300:
            successes += 1
        else:
            print("event failed", r.status_code, r.text)
    return successes, latencies


def get_pool_standings():
    r = session.get(f"{AFF}/pool/standings", timeout=10)
    r.raise_for_status()
    return r.json()


if __name__ == '__main__':
    # Create 3 users
    users = []
    for i in range(3):
        u = create_user(f"testuser{i+1}", f"testuser{i+1}@example.com", f"26097100000{i+1}")
        users.append(u)
        print("Created user:", u.get("id"))

    # Create a business for the first user and use same business for all events
    biz_id = create_business_for_user(users[0].get("id"), name="TestBusiness")
    print("Created business:", biz_id)

    # Create 3 affiliates
    affiliates = []
    for i in range(3):
        aid = create_affiliate(f"affiliate{i+1}", phone=f"2609712000{i+1}")
        affiliates.append(aid)
        print("Created affiliate:", aid)

    # Simulate events per affiliate
    results = {}
    for aid in affiliates:
        succ, lats = send_order_delivered(affiliate_id=aid, business_id=biz_id, count=20)
        print(f"Affiliate {aid}: sent=20 successes={succ} mean_latency={statistics.mean(lats):.3f}s p95={statistics.quantiles(lats, n=100)[94]:.3f}s")
        results[aid] = {"successes": succ, "mean_latency": statistics.mean(lats), "p95": statistics.quantiles(lats, n=100)[94]}

    # Fetch pool standings
    standings = get_pool_standings()
    print("Pool standings summary:")
    print(standings)
