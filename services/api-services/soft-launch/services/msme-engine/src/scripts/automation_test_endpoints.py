#!/usr/bin/env python3
"""
Automation endpoint testers.

Usage: set `BASE_URL` env var or edit BASE_URL constant, then run:

  python automation_test_endpoints.py --run deposit_callback
  python automation_test_endpoints.py --run all

Each endpoint tester is wrapped in a function and returns (ok, response).
If a test fails, the framework will print the response for troubleshooting.
"""
from __future__ import annotations

import os
import time
import json
import argparse
from typing import Callable, Dict, Any, Tuple, Optional

import requests
import uuid


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8500")
TIMEOUT = 5
INTERNAL_SECRET = os.getenv("OUTBOX_INTERNAL_SECRET")


def _attempt_request(method: str, path: str, payload: Optional[Dict] = None, headers: Optional[Dict] = None) -> requests.Response:
    url = BASE_URL.rstrip("/") + path
    headers = headers or {"Content-Type": "application/json"}
    # If an internal secret is configured, automatically add it to outbox/internal calls
    try:
        secret = globals().get("INTERNAL_SECRET")
    except Exception:
        secret = None
    if secret and path.startswith("/outbox"):
        headers.setdefault("X-Internal-Secret", secret)
    if method.upper() == "POST":
        return requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    elif method.upper() == "GET":
        return requests.get(url, params=payload, headers=headers, timeout=TIMEOUT)
    else:
        raise ValueError("Unsupported method")


def wait_for_200(fn: Callable[[], requests.Response], retries: int = 5, backoff: float = 1.0) -> Tuple[bool, Optional[requests.Response]]:
    """Call fn() up to `retries` times until we get a 200-like response. Returns (ok, response).
    """
    for attempt in range(1, retries + 1):
        try:
            resp = fn()
        except Exception as e:
            print(f"Attempt {attempt}: request error: {e}")
            resp = None
        if resp is not None and 200 <= resp.status_code < 300:
            print(f"Attempt {attempt}: OK {resp.status_code}")
            return True, resp
        print(f"Attempt {attempt}: status={getattr(resp, 'status_code', 'ERR')} body={getattr(resp, 'text', '')}")
        time.sleep(backoff)
        backoff *= 1.5
    return False, resp


def test_health() -> Tuple[bool, Optional[requests.Response]]:
    """Simple health check: GET /_health or /."""
    def call():
        # try common health endpoints
        for p in ("/", "/_health", "/health"):
            try:
                r = _attempt_request("GET", p)
            except Exception:
                r = None
            if r is not None and 200 <= r.status_code < 300:
                return r
        # return the last response or raise
        return r

    return wait_for_200(call, retries=3)


def test_deposit_callback(sample_payload: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[requests.Response]]:
    """Test POST /callbacks/payments/deposits. Provide a sample payload or use a sensible default.

    This function is a wrapper so callers can add prerequisite steps before invoking it.
    """
    if sample_payload is None:
        sample_payload = {
            "deposit_id": "test-dep-123",
            "amount": 100.0,
            "currency": "ZMW",
            "status": "COMPLETED",
            "affiliate_id": "aff-test-1",
            "business_id": "biz-test-1",
            "external_id": "ext-123",
            "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "metadata": {"note": "automation-test"},
        }

    def call():
        return _attempt_request("POST", "/callbacks/payments/deposits", payload=sample_payload)

    return wait_for_200(call, retries=6, backoff=1.0)


def test_list_routes() -> Tuple[bool, Optional[requests.Response]]:
    """Call common endpoints that expose route information (openapi/docs/root).
    Try /openapi.json, /docs, then / as a fallback.
    """
    paths = ("/openapi.json", "/docs", "/")

    def call():
        last = None
        for p in paths:
            try:
                r = _attempt_request("GET", p)
            except Exception:
                r = None
            if r is not None and 200 <= r.status_code < 300:
                return r
            last = r
        return last

    return wait_for_200(call, retries=3)


def _unique_suffix() -> str:
    return str(int(time.time() * 1000))


def create_user(username: Optional[str] = None, email: Optional[str] = None, password: str = "Password123") -> Optional[Dict[str, Any]]:
    """Create a user via `POST /auth/register`. Returns parsed JSON on success."""
    if username is None:
        username = f"e2e_{_unique_suffix()}"
    if email is None:
        email = f"{username}@example.com"
    payload = {"username": username, "email": email, "password": password}
    try:
        r = _attempt_request("POST", "/auth/register", payload=payload)
    except Exception as e:
        print("create_user request failed:", e)
        return None
    if 200 <= r.status_code < 300:
        try:
            return r.json()
        except Exception:
            return {"raw": r.text}
    print("create_user failed:", r.status_code, r.text)
    return None


def create_business(name: Optional[str] = None, owner_user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Create a business via `POST /business/register`. Returns parsed JSON on success."""
    if name is None:
        name = f"e2e-biz-{_unique_suffix()}"
    payload = {"owner_user_id": owner_user_id, "name": name}
    try:
        r = _attempt_request("POST", "/business/register", payload=payload)
    except Exception as e:
        print("create_business request failed:", e)
        return None
    if 200 <= r.status_code < 300:
        try:
            return r.json()
        except Exception:
            return {"raw": r.text}
    print("create_business failed:", r.status_code, r.text)
    return None


def test_auth_register_login() -> Tuple[bool, Optional[requests.Response]]:
    """Create a user and then attempt to login. Returns login resp."""
    user = create_user()
    if not user:
        return False, None
    username = user.get("username") or user.get("id")
    payload = {"identifier": username, "password": "Password123"}

    def call():
        return _attempt_request("POST", "/auth/login", payload=payload)

    return wait_for_200(call, retries=3)


def test_business_subscribe() -> Tuple[bool, Optional[requests.Response]]:
    """Create user+business and call subscribe endpoint for the business."""
    user = create_user()
    if not user:
        return False, None
    biz = create_business(owner_user_id=user.get("id"))
    if not biz:
        return False, None
    business_id = biz.get("business", {}).get("id") if isinstance(biz.get("business"), dict) else biz.get("id")
    if not business_id:
        # try common keys
        business_id = biz.get("id")
    payload = {"plan": "paid"}

    def call():
        return _attempt_request("POST", f"/business/{business_id}/subscribe", payload=payload)

    return wait_for_200(call, retries=3)


def test_outbox_pending() -> Tuple[bool, Optional[requests.Response]]:
    """Call GET /outbox/pending and accept 200 or empty results."""
    def call():
        return _attempt_request("GET", "/outbox/pending")

    return wait_for_200(call, retries=2)


ENDPOINTS = {
    "health": test_health,
    "routes": test_list_routes,
    "auth_register_login": test_auth_register_login,
    "business_subscribe": test_business_subscribe,
    "outbox_pending": test_outbox_pending,
    "deposit_callback": test_deposit_callback,
}


def run_all() -> Dict[str, Dict[str, Any]]:
    results = {}
    for name, fn in ENDPOINTS.items():
        print(f"Running {name}...")
        ok, resp = fn()
        results[name] = {"ok": ok, "status_code": getattr(resp, "status_code", None), "body": getattr(resp, "text", None)}
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", help="endpoint name or 'all'", default="all")
    parser.add_argument("--internal-secret", help="override OUTBOX_INTERNAL_SECRET for internal endpoints", default=None)
    args = parser.parse_args()

    # Allow CLI override of the internal secret
    global INTERNAL_SECRET
    if args.internal_secret:
        INTERNAL_SECRET = args.internal_secret

    if args.run == "all":
        results = run_all()
        print(json.dumps(results, indent=2))
        # exit non-zero if any failed
        if not all(r["ok"] for r in results.values()):
            raise SystemExit(1)
    else:
        fn = ENDPOINTS.get(args.run)
        if fn is None:
            print("Unknown endpoint. Known:", list(ENDPOINTS.keys()))
            raise SystemExit(2)
        ok, resp = fn()
        print({"ok": ok, "status_code": getattr(resp, "status_code", None), "body": getattr(resp, "text", None)})
        if not ok:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
