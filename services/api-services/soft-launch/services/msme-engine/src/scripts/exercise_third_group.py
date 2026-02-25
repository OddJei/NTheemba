r"""Exercise read/update/service-token endpoints that require seeded data.

Reads `src/scripts/seed_output.json` for credentials/ids, logs in, and calls
multiple endpoints from the "third group" list. Writes results to
`src/scripts/third_group_output.json`.

Run:
  .\.venv\Scripts\python.exe src\scripts\exercise_third_group.py --base-url http://127.0.0.1:8500
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any, Dict
import requests


DEFAULT_BASE = "http://127.0.0.1:8500"
TIMEOUT = 30


def safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return resp.text


def save_atomic(path: Path, obj: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
    tmp.replace(path)


def main(base_url: str, seed_file: Path, out_file: Path, internal_secret: str | None = None):
    results: Dict[str, Any] = {}
    if not seed_file.exists():
        print(f"Seed file not found: {seed_file}")
        return 1
    seed = json.loads(seed_file.read_text(encoding="utf-8"))

    auth_req = seed.get("auth", {}).get("request", {})
    phone = auth_req.get("phone")
    password = auth_req.get("password")
    user_id = seed.get("auth", {}).get("body", {}).get("id")
    msme_business_id = seed.get("msme_onboard", {}).get("body", {}).get("business", {}).get("id")
    # prefer business id used in deposit callback if it's a UUID; otherwise we'll try to resolve by name
    deposit_biz = seed.get("deposit", {}).get("request", {}).get("business_id")
    business_id: str | None = None
    import re
    uuid_re = re.compile(r"^[0-9a-fA-F-]{36}$")
    if isinstance(deposit_biz, str) and uuid_re.match(deposit_biz):
        business_id = deposit_biz
    else:
        # fallback to msme_onboard business id
        business_id = msme_business_id
    results["seed_file"] = str(seed_file)

    # 1) Login
    print("POST /auth/login")
    r = requests.post(f"{base_url.rstrip('/')}/auth/login", json={"identifier": phone, "password": password}, timeout=TIMEOUT)
    results["login"] = {"status": r.status_code, "body": safe_json(r)}
    access = None
    refresh = None
    if r.status_code == 200:
        j = r.json()
        access = j.get("access_token") or j.get("token") or j.get("access")
        refresh = j.get("refresh_token") or j.get("refresh")

    headers = {"Authorization": f"Bearer {access}"} if access else {}
    # ensure business_headers is always defined to avoid possibly-unbound-variable warnings
    business_headers = headers

    # helper to call internal businesses if we need to resolve a business name
    def lookup_business_by_name(name: str) -> str | None:
        secret = internal_secret or None
        if not secret:
            return None
        try:
            r = requests.get(f"{base_url.rstrip('/')}/internal/businesses", headers={"X-Internal-Secret": secret}, timeout=TIMEOUT)
            if r.status_code == 200:
                for b in r.json():
                    if b.get("name") == name or b.get("phone") == name:
                        return b.get("id")
        except Exception:
            return None
        return None

    # 2) GET /auth/me
    print("GET /auth/me")
    r = requests.get(f"{base_url.rstrip('/')}/auth/me", headers=headers, timeout=TIMEOUT)
    results["auth_me"] = {"status": r.status_code, "body": safe_json(r)}

    # 3) POST /auth/service-token/{business_id} and /auth/service-token/{user_id}
    # If deposit used a business name, try to resolve it using internal endpoint
    if not business_id and isinstance(deposit_biz, str) and deposit_biz:
        resolved = lookup_business_by_name(deposit_biz)
        if resolved:
            business_id = resolved
    business_token = None
    if business_id:
        print(f"POST /auth/service-token/{business_id}")
        r = requests.post(f"{base_url.rstrip('/')}/auth/service-token/{business_id}", json={}, headers=headers, timeout=TIMEOUT)
        results["service_token_business"] = {"status": r.status_code, "body": safe_json(r)}
        if r.status_code == 200:
            j = r.json()
            business_token = j.get("access_token") or j.get("token") or j.get("access")
    # For user service token, try the seeded auth user first; if 404, try the msme_onboard user
    if user_id:
        print(f"POST /auth/service-token/{user_id}")
        r = requests.post(f"{base_url.rstrip('/')}/auth/service-token/{user_id}", json={}, headers=headers, timeout=TIMEOUT)
        results["service_token_user"] = {"status": r.status_code, "body": safe_json(r)}
        if r.status_code == 404:
            # try msme onboard user id
            msme_user_id = seed.get("msme_onboard", {}).get("body", {}).get("user", {}).get("id")
            if msme_user_id:
                print(f"Retry POST /auth/service-token with msme user id {msme_user_id}")
                r2 = requests.post(f"{base_url.rstrip('/')}/auth/service-token/{msme_user_id}", json={}, headers=headers, timeout=TIMEOUT)
                results["service_token_user_msme_attempt"] = {"status": r2.status_code, "body": safe_json(r2)}

    # 4) GET /auth/phone/{phone}
    if phone:
        print(f"GET /auth/phone/{phone}")
        r = requests.get(f"{base_url.rstrip('/')}/auth/phone/{phone}", timeout=TIMEOUT)
        results["auth_phone"] = {"status": r.status_code, "body": safe_json(r)}

    # 5) GET /business/{id}
    if business_id:
        print(f"GET /business/{business_id}")
        # Use business service token for business-scoped operations if available
        business_headers = {"Authorization": f"Bearer {business_token}"} if business_token else headers
        r = requests.get(f"{base_url.rstrip('/')}/business/{business_id}", headers=business_headers, timeout=TIMEOUT)
        results["business_get"] = {"status": r.status_code, "body": safe_json(r)}

        # 6) PUT /business/{id} (update location)
        print(f"PUT /business/{business_id}")
        payload = {"location": "Automation-Update"}
        r = requests.put(f"{base_url.rstrip('/')}/business/{business_id}", json=payload, headers=business_headers, timeout=TIMEOUT)
        results["business_put"] = {"status": r.status_code, "body": safe_json(r)}

        # 7) GET subscription /entitlements /metadata
        r = requests.get(f"{base_url.rstrip('/')}/business/{business_id}/subscription", headers=headers, timeout=TIMEOUT)
        results["business_subscription"] = {"status": r.status_code, "body": safe_json(r)}
        r = requests.get(f"{base_url.rstrip('/')}/business/{business_id}/entitlements", headers=headers, timeout=TIMEOUT)
        results["business_entitlements"] = {"status": r.status_code, "body": safe_json(r)}
        r = requests.get(f"{base_url.rstrip('/')}/business/{business_id}/metadata", headers=headers, timeout=TIMEOUT)
        results["business_metadata"] = {"status": r.status_code, "body": safe_json(r)}

        # 8) GET events for business
        r = requests.get(f"{base_url.rstrip('/')}/events/business/{business_id}", headers=headers, timeout=TIMEOUT)
        results["events_business"] = {"status": r.status_code, "body": safe_json(r)}

    # 9) GET business by owner phone
    if phone:
        print(f"GET /business/phone/{phone}")
        r = requests.get(f"{base_url.rstrip('/')}/business/phone/{phone}", timeout=TIMEOUT)
        results["business_by_phone"] = {"status": r.status_code, "body": safe_json(r)}

    # 10) Notification reads
    if user_id:
        r = requests.get(f"{base_url.rstrip('/')}/notification/user/{user_id}", headers=headers, timeout=TIMEOUT)
        results["notification_user"] = {"status": r.status_code, "body": safe_json(r)}

    # 11) Delivery locations update/get
    if business_id:
        print(f"PUT /businesses/{business_id}/delivery-locations")
        # API expects `delivery_locations` mapping of town -> metadata
        payload = {
            "delivery_locations": {
                "Lusaka": {"price_minor": 2500, "currency": "ZMW"},
                "Kitwe": {"price_minor": 3500, "currency": "ZMW"}
            }
        }
        # Try with business-scoped token first (if available), then fall back to user token.
        def _do_put(headers_to_use):
            try:
                return requests.put(f"{base_url.rstrip('/')}/businesses/{business_id}/delivery-locations", json=payload, headers=headers_to_use, timeout=TIMEOUT)
            except Exception as e:
                return e

        primary_headers = business_headers if business_token else headers
        secondary_headers = headers if business_token else (business_headers if business_headers != headers else None)

        r = _do_put(primary_headers)
        if isinstance(r, Exception):
            results["delivery_locations_put"] = {"error": str(r)}
        else:
            results["delivery_locations_put"] = {"status": r.status_code, "body": safe_json(r)}
            # If forbidden, retry with the alternate auth header to handle token semantics differences
            if r.status_code == 403 and secondary_headers:
                print("Delivery locations PUT returned 403; retrying with alternate auth header...")
                r2 = _do_put(secondary_headers)
                if isinstance(r2, Exception):
                    results["delivery_locations_put_retry"] = {"error": str(r2)}
                else:
                    results["delivery_locations_put_retry"] = {"status": r2.status_code, "body": safe_json(r2)}
        r = requests.get(f"{base_url.rstrip('/')}/businesses/{business_id}/delivery-locations", headers=headers, timeout=TIMEOUT)
        results["delivery_locations_get"] = {"status": r.status_code, "body": safe_json(r)}

        # 12) POST /business/reindex
        r = requests.post(f"{base_url.rstrip('/')}/business/reindex", json={"business_ids": [business_id]}, headers=headers, timeout=TIMEOUT)
        results["business_reindex"] = {"status": r.status_code, "body": safe_json(r)}

    # 13) Outbox ack (ack first pending id if present)
    outbox = seed.get("outbox_pending", {}).get("body")
    if isinstance(outbox, list) and outbox:
        first = outbox[0].get("id")
        if first:
            print(f"POST /outbox/ack id={first}")
            ack_headers = {}
            if internal_secret:
                ack_headers["X-Internal-Secret"] = internal_secret
            r = requests.post(f"{base_url.rstrip('/')}/outbox/ack", json={"ids": [first]}, headers=ack_headers, timeout=TIMEOUT)
            results["outbox_ack"] = {"status": r.status_code, "body": safe_json(r)}

    # 14) Internal notification broadcasts: all, role, user
    # Use internal secret header when provided so internal endpoints authenticate.
    secret_headers = {"X-Internal-Secret": internal_secret} if internal_secret else {}
    notify_payload = {"channel": "email", "template": "automation_blast", "payload": {"subject": "Automation test", "body": "This is a test broadcast"}}

    print("POST /internal/notifications/broadcast/all")
    try:
        r = requests.post(f"{base_url.rstrip('/')}/internal/notifications/broadcast/all", json=notify_payload, headers=secret_headers, timeout=TIMEOUT)
        results["notification_broadcast_all"] = {"status": r.status_code, "body": safe_json(r)}
    except Exception as e:
        results["notification_broadcast_all"] = {"error": str(e)}

    print("POST /internal/notifications/broadcast/role/admin")
    try:
        r = requests.post(f"{base_url.rstrip('/')}/internal/notifications/broadcast/role/admin", json=notify_payload, headers=secret_headers, timeout=TIMEOUT)
        results["notification_broadcast_role_admin"] = {"status": r.status_code, "body": safe_json(r)}
    except Exception as e:
        results["notification_broadcast_role_admin"] = {"error": str(e)}

    if user_id:
        print(f"POST /internal/notifications/broadcast/user/{user_id}")
        try:
            r = requests.post(f"{base_url.rstrip('/')}/internal/notifications/broadcast/user/{user_id}", json=notify_payload, headers=secret_headers, timeout=TIMEOUT)
            results["notification_broadcast_user"] = {"status": r.status_code, "body": safe_json(r)}
        except Exception as e:
            results["notification_broadcast_user"] = {"error": str(e)}

    # 15) Delete / teardown endpoints (best-effort). Use business-scoped token if available.
    if user_id or business_id:
        # try deleting seeded user
        if user_id:
            print(f"DELETE /auth/user/{user_id}")
            try:
                r = requests.delete(f"{base_url.rstrip('/')}/auth/user/{user_id}", headers=business_headers if business_token else headers, timeout=TIMEOUT)
                results["delete_user"] = {"status": r.status_code, "body": safe_json(r)}
            except Exception as e:
                results["delete_user"] = {"error": str(e)}

        # try deleting seeded business
        if business_id:
            print(f"DELETE /business/{business_id}")
            try:
                r = requests.delete(f"{base_url.rstrip('/')}/business/{business_id}", headers=business_headers if business_token else headers, timeout=TIMEOUT)
                results["delete_business"] = {"status": r.status_code, "body": safe_json(r)}
            except Exception as e:
                results["delete_business"] = {"error": str(e)}

    save_atomic(out_file, results)
    print(f"Wrote results to {out_file}")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default=DEFAULT_BASE)
    p.add_argument("--seed-file", default="src/scripts/seed_output.json")
    p.add_argument("--out-file", default="src/scripts/third_group_output.json")
    p.add_argument("--internal-secret", default=None, help="X-Internal-Secret value for internal endpoints")
    args = p.parse_args()
    seed_path = Path(args.seed_file)
    out_path = Path(args.out_file)
    raise SystemExit(main(args.base_url, seed_path, out_path, args.internal_secret))
