import time
import uuid

import httpx


def main() -> None:
    base = "http://localhost:8500"

    suffix = uuid.uuid4().hex[:8]
    user = {
        "username": f"testowner_{suffix}",
        "email": f"owner_{suffix}@test.com",
        "phone": f"+260999{suffix[:6]}",
        "password": "Test123!",
    }

    r = httpx.post(f"{base}/auth/register", json=user, timeout=15)
    print("register", r.status_code)
    r.raise_for_status()
    user_id = r.json()["id"]

    biz = {
        "name": f"Test MSME {suffix}",
        "owner_user_id": user_id,
        "location": "Lusaka",
        "category": "retail",
        "subscription_plan": "free",
    }
    r = httpx.post(f"{base}/business/register", json=biz, timeout=15)
    print("business_register", r.status_code)
    r.raise_for_status()

    obj = r.json()
    business_id = obj["business"]["id"]
    print("business_id", business_id)

    login = {"identifier": user["email"], "password": user["password"]}
    r = httpx.post(f"{base}/auth/login", json=login, timeout=15)
    print("login", r.status_code)
    r.raise_for_status()
    token = r.json()["access_token"]

    sub = {
        "plan": "paid",
        "amount_minor": 1000,
        "phone_number": user["phone"],
        "provider": "pawa",
        "currency": "ZMW",
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Correlation-Id": f"audit-test-{suffix}",
    }

    r = httpx.post(
        f"{base}/business/{business_id}/subscribe_and_pay",
        json=sub,
        headers=headers,
        timeout=15,
    )
    print("subscribe_and_pay", r.status_code)
    print(r.text)

    # Give async audit emits a moment
    time.sleep(1.5)
    print("done")


if __name__ == "__main__":
    main()
