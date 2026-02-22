"""Simple integration test: fetch business ids from msme-engine and bulk-create products in catalog-inventory.

Usage:
  python tools/integration_test.py

Requires services to be available at these URLs (compose defaults):
  MSME: http://localhost:8500
  CATALOG: http://localhost:8520

The script will:
 - GET /internal/business on msme-engine to collect business ids
 - For the first N business ids, POST multiple products to /catalog/product
 - Report successes and failures
"""

import asyncio
import random
import uuid
import os
from pathlib import Path

import httpx


def _load_root_env() -> None:
    root_env = Path(__file__).resolve().parents[1] / ".env"
    if not root_env.exists():
        return
    for line in root_env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_root_env()

MSME_BASE = os.environ.get("MSME_BASE_URL", "http://localhost:8500")
CATALOG_BASE = os.environ.get("CATALOG_BASE_URL", "http://localhost:8520")

BULK_PER_BUSINESS = int(os.environ.get("BULK_PER_BUSINESS", "3"))
BUSINESS_LIMIT = int(os.environ.get("BUSINESS_LIMIT", "3"))


async def fetch_access_token() -> str:
    identifier = os.environ.get("MSME_SERVICE_IDENTIFIER")
    password = os.environ.get("MSME_SERVICE_PASSWORD")
    if not identifier or not password:
        raise RuntimeError("Missing MSME_SERVICE_IDENTIFIER or MSME_SERVICE_PASSWORD")

    url = f"{MSME_BASE.rstrip('/')}/auth/login"
    payload = {
        "identifier": identifier,
        "password": password,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"No access_token in login response: {data}")
        return token

async def fetch_businesses():
    url = f"{MSME_BASE.rstrip('/')}/internal/businesses"
    async with httpx.AsyncClient(timeout=10.0) as client:
        # internal endpoints require X-Internal-Secret
        headers = {"X-Internal-Secret": os.environ.get("OUTBOX_INTERNAL_SECRET", "secret")}
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        return r.json()

async def create_product(business_id: str, access_token: str):
    url = f"{CATALOG_BASE.rstrip('/')}/catalog/product"
    payload = {
        "business_id": business_id,
        "name": f"Test Product {uuid.uuid4().hex[:6]}",
        "description": "Integration test product",
        "price": float(random.randint(100, 1000)),
        "currency": "ZMW",
        "tags": ["integration", "test"],
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    # Support catalog's test shortcut: when using the dummy token, include X-Business-Id and X-Role
    if access_token == "dummy-token":
        headers["X-Business-Id"] = business_id
        headers["X-Role"] = os.environ.get("TEST_ROLE", "msme")
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, json=payload, headers=headers)
        return r.status_code, r.text

async def main():
    print(f"Using MSME: {MSME_BASE}, Catalog: {CATALOG_BASE}")
    use_dummy = False
    try:
        access_token = await fetch_access_token()
    except Exception as e:
        print("Failed to authenticate against MSME /auth/login, falling back to dummy-token:", e)
        access_token = "dummy-token"
        use_dummy = True

    try:
        businesses = await fetch_businesses()
    except Exception as e:
        print("Failed to fetch businesses:", e)
        return

    # Expect businesses to be a list of objects with `id` or `business_id` field
    ids = []
    for b in businesses:
        if isinstance(b, dict):
            if "id" in b:
                ids.append(b["id"])
            elif "business_id" in b:
                ids.append(b["business_id"])
    if not ids:
        print("No business ids found from msme-engine response. Response:", businesses)
        return

    ids = ids[:BUSINESS_LIMIT]
    print(f"Using {len(ids)} business ids: {ids}")

    results = []
    for bid in ids:
        for i in range(BULK_PER_BUSINESS):
            try:
                status, text = await create_product(bid, access_token)
                results.append((bid, status, text))
                print(f"Created product for {bid}: status={status}")
            except Exception as e:
                results.append((bid, None, str(e)))
                print(f"Failed create for {bid}: {e}")

    # Summary
    ok = [r for r in results if r[1] and 200 <= r[1] < 300]
    failed = [r for r in results if not (r[1] and 200 <= r[1] < 300)]
    print("\nSummary:")
    print(f"  Attempts: {len(results)}")
    print(f"  Successes: {len(ok)}")
    print(f"  Failures: {len(failed)}")
    if failed:
        print("Failures details:")
        for f in failed:
            print(f)

if __name__ == '__main__':
    asyncio.run(main())
