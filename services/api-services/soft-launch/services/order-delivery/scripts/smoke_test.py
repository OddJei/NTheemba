import time
import sys
import httpx

BASE = "http://127.0.0.1:8540"

client = httpx.Client(timeout=10.0)


def wait_health(timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = client.get(f"{BASE}/health")
            if r.status_code == 200 and r.json().get("status") == "ok":
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


if __name__ == "__main__":
    if not wait_health():
        print("health failed", file=sys.stderr)
        sys.exit(2)

    order_payload = {
        "session_id": "sess_smoke",
        "user_phone": "+27000000000",
        "user_id": None,
        "business_id": "business_smoke",
        "delivery_method": "pickup",
        "total_amount": 12500,
        "currency": "ZAR",
        "metadata": {"cart_id": "cart_smoke"},
    }

    r = client.post(f"{BASE}/orders/create", json=order_payload)
    r.raise_for_status()
    order = r.json()
    print("order created", order.get("id"))

    r = client.post(f"{BASE}/orders/{order['id']}/mark_paid")
    r.raise_for_status()
    print("order paid")

    r = client.post(f"{BASE}/delivery/initiate/{order['id']}")
    r.raise_for_status()
    init = r.json()
    print("delivery initiated", init.get("delivery", {}).get("id"))
    code = init.get("delivery_code")
    if not code or code == "******":
        print("missing delivery code", file=sys.stderr)
        sys.exit(3)

    r = client.post(f"{BASE}/delivery/{init['delivery']['id']}/confirm", json={"delivery_code": code, "confirmed_by": "smoke_test"})
    r.raise_for_status()
    print("delivery confirmed")

    r = client.get(f"{BASE}/orders/{order['id']}")
    r.raise_for_status()
    print("order status", r.json().get("status"))

    print("SMOKE_OK")
