import os
import time
import json
import asyncio
from typing import Any

import httpx

BASE_MSME = os.getenv("MSME_BASE_URL", "http://localhost:8500")
BASE_CATALOG = os.getenv("CATALOG_BASE_URL", "http://localhost:8520")
OUTBOX_SECRET = os.getenv("OUTBOX_INTERNAL_SECRET")


def load_env_dotenv():
    # try to load workspace .env if present
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if os.path.exists(env_path):
        with open(env_path) as f:
            for ln in f:
                ln = ln.strip()
                if not ln or ln.startswith('#'):
                    continue
                if '=' in ln:
                    k, v = ln.split('=', 1)
                    os.environ.setdefault(k, v)


async def fetch_businesses(client: httpx.AsyncClient) -> list[str]:
    # Try several possible internal-secret env keys used in this workspace
    secrets = [
        os.getenv("OUTBOX_INTERNAL_SECRET"),
        os.getenv("X_INTERNAL_SECRET"),
        os.getenv("INTERNAL_SERVICE_SECRET"),
    ]
    secrets = [s for s in secrets if s]
    if not secrets:
        # try reading .env directly
        env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
        if os.path.exists(env_file):
            with open(env_file) as f:
                for ln in f:
                    if "OUTBOX_INTERNAL_SECRET" in ln or "X_INTERNAL_SECRET" in ln or "INTERNAL_SERVICE_SECRET" in ln:
                        k, v = ln.strip().split("=", 1)
                        secrets.append(v)

    last_exc = None
    for sec in secrets:
        headers = {"X-Internal-Secret": sec}
        try:
            r = await client.get(f"{BASE_MSME}/internal/businesses", headers=headers)
            r.raise_for_status()
            data = r.json()
            return [b["id"] for b in data]
        except Exception as e:
            last_exc = e
            continue
    # if none worked, raise the last exception
    if last_exc:
        raise last_exc
    raise RuntimeError("no internal secret available to call msme internal endpoints")


async def run_tests():
    async with httpx.AsyncClient(timeout=10.0) as client:
        # fetch businesses
        try:
            businesses = await fetch_businesses(client)
        except Exception as e:
            print("FAILED to fetch businesses:", e)
            return

        if not businesses:
            print("No businesses found; aborting tests")
            return

        biz = businesses[0]
        print("Using business:", biz)

        headers = {"Authorization": f"Bearer dummy-token"}

        results: list[tuple[str, int, Any]] = []

        # 1) Category create
        cat_payload = {"business_id": biz, "name": "Test Cat", "description": "desc"}
        r = await client.post(f"{BASE_CATALOG}/catalog/category", json=cat_payload, headers=headers)
        results.append(("category_create", r.status_code, r.text))
        if r.status_code == 201:
            cat = r.json()
            cat_id = cat.get("id")
        else:
            cat_id = None

        # 2) Category update
        if cat_id:
            r = await client.put(f"{BASE_CATALOG}/catalog/category/{cat_id}", json={"name": "Test Cat Updated"}, headers=headers)
            results.append(("category_update", r.status_code, r.text))

        # 3) Category delete
        if cat_id:
            r = await client.delete(f"{BASE_CATALOG}/catalog/category/{cat_id}", headers=headers)
            results.append(("category_delete", r.status_code, r.text))

        # 4) Product create
        prod_payload = {"business_id": biz, "category_id": None, "name": "Test Product", "description": "pdesc", "price": 100, "currency": "NGN", "image_url": None, "tags": []}
        r = await client.post(f"{BASE_CATALOG}/catalog/product", json=prod_payload, headers=headers)
        results.append(("product_create", r.status_code, r.text))
        prod_id = None
        if r.status_code == 201:
            prod_id = r.json().get("id")

        # 5) Product update
        if prod_id:
            r = await client.put(f"{BASE_CATALOG}/catalog/product/{prod_id}", json={"name": "Test Product V2"}, headers=headers)
            results.append(("product_update", r.status_code, r.text))

        # 6) Variant add
        variant_id = None
        if prod_id:
            from uuid import uuid4
            sku = f"SKU-{uuid4().hex[:8]}"
            r = await client.post(f"{BASE_CATALOG}/catalog/product/{prod_id}/variant", json={"name": "Default", "sku": sku}, headers=headers)
            results.append(("variant_add", r.status_code, r.text))
            if r.status_code == 201:
                variant_id = r.json().get("id")

        # 7) Inventory update -> set stock to 0 (out_of_stock) and then restock
        if variant_id:
            r = await client.post(f"{BASE_CATALOG}/inventory/update", json={"variant_id": variant_id, "delta": 0, "reserved_delta": 0, "threshold": 0}, headers=headers)
            results.append(("inventory_nochange", r.status_code, r.text))

            r = await client.post(f"{BASE_CATALOG}/inventory/update", json={"variant_id": variant_id, "delta": -10}, headers=headers)
            results.append(("inventory_decrease", r.status_code, r.text))

            r = await client.post(f"{BASE_CATALOG}/inventory/update", json={"variant_id": variant_id, "delta": 20}, headers=headers)
            results.append(("inventory_increase", r.status_code, r.text))

        # 8) Uploads complete to trigger image.updated
        if prod_id:
            try:
                r = await client.post(f"{BASE_CATALOG}/uploads/complete", json={"key": "uploads/test.jpg", "product_id": prod_id}, headers=headers)
                results.append(("uploads_complete", r.status_code, r.text))
            except Exception as e:
                results.append(("uploads_complete", 0, f"error: {e}"))

        # 9) Reindex
        r = await client.post(f"{BASE_CATALOG}/catalog/reindex/{biz}", json={}, headers=headers)
        results.append(("reindex", r.status_code, r.text))

        # print results
        for name, status, body in results:
            print(f"{name}: {status}")
            try:
                print(json.dumps(json.loads(body), indent=2))
            except Exception:
                print(body[:500])


if __name__ == "__main__":
    load_env_dotenv()
    asyncio.run(run_tests())
