import asyncio
import uuid
import sys
import json

import httpx

import os

BASE = os.getenv("CART_BASE_URL", "http://127.0.0.1:8530")
MSME_BASE = os.getenv("MSME_BASE_URL", "http://127.0.0.1:8500").rstrip("/")
INTERNAL_SECRET = os.getenv("OUTBOX_INTERNAL_SECRET", os.getenv("X_INTERNAL_SECRET", ""))

async def run():
    client = httpx.AsyncClient(timeout=10.0)
    ok = True
    try:
        print("GET /health ->", end=" ")
        r = await client.get(f"{BASE}/health")
        print(r.status_code, r.text)
        if r.status_code != 200:
            ok = False

        print("GET /metrics ->", end=" ")
        r = await client.get(f"{BASE}/metrics")
        print(r.status_code, "(metrics returned)" if r.status_code==200 else r.text)
        if r.status_code != 200:
            ok = False

        session_id = f"sess-{uuid.uuid4().hex[:8]}"
        # Try to discover a business via MSME internal endpoint (if secret present)
        business_id = "biz-test-1"
        variant_id = "variant-test-1"
        if INTERNAL_SECRET:
            try:
                h = {"X-Internal-Secret": INTERNAL_SECRET}
                r = await client.get(f"{MSME_BASE}/internal/businesses", headers=h)
                if r.status_code == 200 and isinstance(r.json(), list) and r.json():
                    businesses = r.json()
                    for b in businesses:
                        bid = b.get("id")
                        if not bid:
                            continue
                        # fetch products for that business from catalog-inventory (public path)
                        r2 = await client.get(f"http://127.0.0.1:8520/catalog/business/{bid}")
                        if r2.status_code != 200:
                            continue
                        j = r2.json()
                        variants = j.get("variants") or []
                        if variants:
                            business_id = bid
                            variant_id = variants[0].get("id")
                            break
            except Exception:
                pass

        cart_payload = {"session_id": session_id, "user_phone": "+260971000001", "business_id": business_id}
        print("POST /cart/create ->", end=" ")
        r = await client.post(f"{BASE}/cart/create", json=cart_payload)
        print(r.status_code, r.text)
        if r.status_code not in (200,201):
            ok = False
            return 1
        cart = r.json()
        cart_id = cart.get("id") or cart.get("id")
        print("created cart id:", cart_id)

        print("POST /cart/{cart_id}/add ->", end=" ")
        add_payload = {"variant_id": variant_id, "quantity": 2, "unit_price": 100.0}
        r = await client.post(f"{BASE}/cart/{cart_id}/add", json=add_payload)
        print(r.status_code, r.text)
        if r.status_code != 200:
            ok = False
            return 1
        item = r.json()
        item_id = item.get("id") or item.get("id")
        print("added item id:", item_id)

        print("GET /cart/session/{session_id} ->", end=" ")
        r = await client.get(f"{BASE}/cart/session/{session_id}")
        print(r.status_code, r.text[:200])
        if r.status_code != 200:
            ok = False

        print("POST /cart/{cart_id}/checkout ->", end=" ")
        r = await client.post(f"{BASE}/cart/{cart_id}/checkout")
        print(r.status_code, r.text)
        if r.status_code != 200:
            ok = False

        # Try listing by user
        print("GET /cart/user/{user_phone} ->", end=" ")
        r = await client.get(f"{BASE}/cart/user/+260971000001")
        print(r.status_code, "items:", len(r.json()) if r.status_code==200 else r.text)
        if r.status_code != 200:
            ok = False

        # Try removing item (best-effort): find a cart and item
        try:
            carts = (await client.get(f"{BASE}/cart/user/+260971000001")).json()
            if carts:
                cid = carts[0].get("id")
                items = (await client.get(f"{BASE}/cart/session/{session_id}")).json()
                if items:
                    # if cart items endpoint returned items, try remove
                    # Note: remove endpoint expects item id path; we try if present
                    item_id = items[0].get("id")
                    print("DELETE /cart/{cart_id}/remove/{item_id} ->", end=" ")
                    r = await client.delete(f"{BASE}/cart/{cid}/remove/{item_id}")
                    print(r.status_code, r.text)
        except Exception:
            pass

    finally:
        await client.aclose()

    print("\nSummary: OK" if ok else "\nSummary: FAIL")
    return 0 if ok else 2

if __name__ == '__main__':
    code = asyncio.run(run())
    sys.exit(code)
