"""Seed a few dummy records via the msme-engine HTTP API and persist results.

This script issues example POSTs to commonly used seeding endpoints, prints
responses and writes a JSON file with IDs/credentials for downstream tests.

Run from repository root:
  .\.venv\Scripts\python.exe src\scripts\seed_dummy_data.py --base-url http://127.0.0.1:8500 --out-file src/scripts/seed_output.json
"""
from __future__ import annotations
import argparse
import json
from typing import Any, Dict
from pathlib import Path
import requests
import os
import secrets
import uuid


def _rand_suffix() -> str:
    return uuid.uuid4().hex[:8]


def _rand_phone() -> str:
    return f"+260971{secrets.randbelow(10**6):06d}"


DEFAULT_BASE = "http://127.0.0.1:8500"
TIMEOUT = 30


def try_post(path: str, payload: Any, base_url: str = DEFAULT_BASE, headers=None):
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    print(f"POST {url}")
    try:
        resp = requests.post(url, json=payload, headers=headers or {}, timeout=TIMEOUT)
    except Exception as e:
        print(f"  Request failed: {e}")
        return None
    print(f"  -> {resp.status_code} {resp.reason}")
    try:
        print("  Body:", json.dumps(resp.json(), indent=2))
    except Exception:
        text = resp.text or ""
        print("  Body (raw):", text[:1000])
    return resp


def try_get(path: str, base_url: str = DEFAULT_BASE, headers=None):
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    print(f"GET {url}")
    try:
        resp = requests.get(url, headers=headers or {}, timeout=TIMEOUT)
    except Exception as e:
        print(f"  Request failed: {e}")
        return None
    print(f"  -> {resp.status_code} {resp.reason}")
    try:
        print("  Body:", json.dumps(resp.json(), indent=2))
    except Exception:
        text = resp.text or ""
        print("  Body (raw):", text[:1000])
    return resp


def _body_or_text(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return resp.text


def main(base_url: str, out_file: Path | None = None, internal_secret: str | None = None) -> Dict[str, Any]:
    outputs: Dict[str, Any] = {}

    # 1) Register a user
    s_user = _rand_suffix()
    user_phone = _rand_phone()
    password = "pass1234"
    user_payload = {
        "phone": user_phone,
        "name": "seed-user",
        "username": f"seeduser_{s_user}",
        "email": f"seed-user-{s_user}@example.com",
        "password": password,
    }
    auth_resp = try_post("auth/register", user_payload, base_url)
    outputs["auth"] = {"request": user_payload}
    if auth_resp is not None:
        outputs["auth"]["status"] = auth_resp.status_code
        outputs["auth"]["body"] = _body_or_text(auth_resp)
        outputs["auth"]["password"] = password

    # 2) Onboard an affiliate
    s_aff = _rand_suffix()
    aff_phone = _rand_phone()
    aff_payload = {
        "profile": {
            "phone": aff_phone,
            "fullName": "Seed Affiliate",
            "username": f"seedaffiliate_{s_aff}",
            "email": f"seed-aff-{s_aff}@example.com",
        },
        "preferences": {"channels": ["email"], "categories": ["promotions"]},
        "affiliate_id": str(uuid.uuid4()),
    }
    aff_resp = try_post("affiliate/onboard", aff_payload, base_url)
    outputs["affiliate"] = {"request": aff_payload}
    if aff_resp is not None:
        outputs["affiliate"]["status"] = aff_resp.status_code
        outputs["affiliate"]["body"] = _body_or_text(aff_resp)

    # 3) MSMe onboard (creates user + business)
    s_msme = _rand_suffix()
    msme_phone = _rand_phone()
    msme_payload = {
        "profile": {"phone": msme_phone, "fullName": "Seed MSME", "username": f"seed-msme-{s_msme}", "email": f"seed-msme-{s_msme}@example.com"},
        "business": {"businessName": f"Seed Business {s_msme}", "phone": _rand_phone(), "location": "Lusaka"},
        "products": [{"name": "Seed Product", "price": str(secrets.randbelow(20000) + 100), "initialStock": str(secrets.randbelow(50) + 1)}],
    }
    msme_resp = try_post("msme/onboard", msme_payload, base_url)
    outputs["msme_onboard"] = {"request": msme_payload}
    if msme_resp is not None:
        outputs["msme_onboard"]["status"] = msme_resp.status_code
        outputs["msme_onboard"]["body"] = _body_or_text(msme_resp)

    # 4) Register a business directly
    s_biz = _rand_suffix()
    biz_phone = _rand_phone()
    biz_payload = {
        "name": f"Manual Seed Biz {s_biz}",
        "phone": biz_phone,
        "owner": {"phone": user_payload["phone"], "name": user_payload["name"], "username": user_payload["username"], "email": user_payload["email"], "password": user_payload["password"]},
        "location": "Lusaka",
    }
    biz_resp = try_post("business/register", biz_payload, base_url)
    outputs["business_register"] = {"request": biz_payload}
    if biz_resp is not None:
        outputs["business_register"]["status"] = biz_resp.status_code
        outputs["business_register"]["body"] = _body_or_text(biz_resp)

    # 5) Simulate a deposit callback (payments)
    deposit_payload = {
        "event_type": "deposit.created",
        "event_id": f"evt-seed-{_rand_suffix()}",
        "depositId": f"dep-seed-{_rand_suffix()}",
        "business_id": biz_payload.get("name") or "test-biz",
        "amount_minor": 10000,
        "currency": "ZMW",
        "status": "completed",
    }
    dep_resp = try_post("callbacks/payments/deposits", deposit_payload, base_url)
    outputs["deposit"] = {"request": deposit_payload}
    if dep_resp is not None:
        outputs["deposit"]["status"] = dep_resp.status_code
        outputs["deposit"]["body"] = _body_or_text(dep_resp)

    # Internal diagnostic endpoints (capture returned data if available)
    # CLI-provided secret takes precedence; otherwise fall back to env var
    internal_secret = internal_secret or os.environ.get("OUTBOX_INTERNAL_SECRET")
    try:
        resp = try_get("_debug/env", base_url)
        outputs["_debug_env"] = {"status": resp.status_code, "body": _body_or_text(resp)} if resp is not None else {"error": "failed"}
    except Exception:
        outputs["_debug_env"] = {"error": "failed"}

    try:
        headers = {"X-Internal-Secret": internal_secret} if internal_secret else None
        resp = try_get("outbox/pending", base_url, headers=headers)
        outputs["outbox_pending"] = {"status": resp.status_code, "body": _body_or_text(resp)} if resp is not None else {"error": "failed"}
    except Exception:
        outputs["outbox_pending"] = {"error": "failed"}

    try:
        headers = {"X-Internal-Secret": internal_secret} if internal_secret else None
        resp = try_get("internal/businesses", base_url, headers=headers)
        outputs["internal_businesses"] = {"status": resp.status_code, "body": _body_or_text(resp)} if resp is not None else {"error": "failed"}
    except Exception:
        outputs["internal_businesses"] = {"error": "failed"}

    try:
        headers = {"X-Internal-Secret": internal_secret} if internal_secret else None
        resp = try_get("internal/affiliates", base_url, headers=headers)
        outputs["internal_affiliates"] = {"status": resp.status_code, "body": _body_or_text(resp)} if resp is not None else {"error": "failed"}
    except Exception:
        outputs["internal_affiliates"] = {"error": "failed"}

    # Persist outputs atomically (overwrite previous file)
    if out_file:
        try:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = out_file.with_suffix(out_file.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(outputs, fh, indent=2, ensure_ascii=False)
            tmp.replace(out_file)
            print(f"Saved seed output to {out_file}")
        except Exception as e:
            print(f"Failed to write seed output file {out_file}: {e}")

    return outputs


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default=DEFAULT_BASE)
    p.add_argument("--out-file", default=None, help="Path to write JSON seed output")
    p.add_argument("--internal-secret", default=None, help="Value to use for X-Internal-Secret when calling internal endpoints")
    args = p.parse_args()
    out_path = Path(args.out_file) if args.out_file else (Path(__file__).resolve().parent / "seed_output.json")
    main(args.base_url, out_path, args.internal_secret)
