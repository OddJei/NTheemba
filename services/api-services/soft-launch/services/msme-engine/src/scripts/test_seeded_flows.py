"""Test common seeded flows: login, auth/me, lookup by phone, set subscription price, subscribe.

Reads `seed_output.json` produced by the seeder to discover phone/password.
Run from repository root:
  .\.venv\Scripts\python.exe src\scripts\test_seeded_flows.py --base-url http://127.0.0.1:8500 --seed-file src/scripts/seed_output.json
"""
import argparse
import json
from pathlib import Path
import requests


DEFAULT_BASE = "http://127.0.0.1:8500"
TIMEOUT = 30


def safe_print(resp: requests.Response):
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    print(f"  -> {resp.status_code} {resp.reason}")
    print("  Body:", json.dumps(body, indent=2) if isinstance(body, (dict, list)) else body)


def main(base_url: str, seed_file: Path | None = None):
    phone = "+260971000005"
    password = "pass1234"

    if seed_file and seed_file.exists():
        try:
            with seed_file.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            # Try to extract auth phone/password from seed output
            auth = data.get("auth", {})
            body = auth.get("body") if isinstance(auth.get("body"), dict) else None
            if body and body.get("phone"):
                phone = body.get("phone")
            # fall back to stored request data
            elif auth.get("request"):
                phone = auth["request"].get("phone", phone)
            password = auth.get("password", password)
            print(f"Using seeded phone={phone}")
        except Exception as e:
            print(f"Failed to read seed file {seed_file}: {e}")

    print("Logging in seeded user (identifier + password):")
    resp = requests.post(f"{base_url.rstrip('/')}/auth/login", json={"identifier": phone, "password": password}, timeout=TIMEOUT)
    safe_print(resp)
    if resp.status_code != 200:
        print("Login failed — cannot continue tests")
        return
    data = resp.json()
    token = data.get("access_token") or data.get("token") or data.get("access")
    if not token:
        print("No token found in login response; stopping")
        return
    headers = {"Authorization": f"Bearer {token}"}

    print("Calling /auth/me with access token")
    resp = requests.get(f"{base_url.rstrip('/')}/auth/me", headers=headers, timeout=TIMEOUT)
    safe_print(resp)

    print("Looking up user by phone via /auth/phone")
    resp = requests.get(f"{base_url.rstrip('/')}/auth/phone/{phone}", timeout=TIMEOUT)
    safe_print(resp)

    print("Looking up business by owner phone via /business/phone/")
    resp = requests.get(f"{base_url.rstrip('/')}/business/phone/{phone}", timeout=TIMEOUT)
    safe_print(resp)
    biz = None
    try:
        j = resp.json()
        if isinstance(j, list) and j:
            biz = j[0]
        elif isinstance(j, dict) and j.get("id"):
            biz = j
    except Exception:
        pass

    if biz:
        biz_id = biz.get("id")
        print(f"Found business id: {biz_id}, setting subscription price")
        payload = {"amount_minor": 5000, "currency": "ZMW"}
        resp = requests.put(f"{base_url.rstrip('/')}/business/{biz_id}/subscription_price", json=payload, headers=headers, timeout=TIMEOUT)
        safe_print(resp)

        print("Subscribing business (subscribe_and_pay)")
        resp = requests.post(f"{base_url.rstrip('/')}/business/{biz_id}/subscribe_and_pay", json={"payment_provider":"test"}, headers=headers, timeout=TIMEOUT)
        safe_print(resp)
    else:
        print("No business found for seeded phone — skipping business flow")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default=DEFAULT_BASE)
    p.add_argument("--seed-file", default="src/scripts/seed_output.json", help="Path to seed output JSON")
    args = p.parse_args()
    seed_path = Path(args.seed_file)
    main(args.base_url, seed_path)
