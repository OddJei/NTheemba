import time
import httpx

CATALOG = "http://127.0.0.1:8520"
CART = "http://127.0.0.1:8530"
MSME = "http://127.0.0.1:8500"
AFF = "http://127.0.0.1:8510"


def wait_for(url: str, timeout: int = 10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{url}/health", timeout=1.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"service {url} did not become ready")


def test_services_up():
    for url in (CATALOG, CART, MSME, AFF):
        assert wait_for(url, timeout=15)


def test_cart_catalog_checkout_flow():
    # create product
    prod_payload = {"business_id": "test-business", "name": "Test Product", "price": 100.0}
    r = httpx.post(f"{CATALOG}/catalog/product", json=prod_payload, timeout=5.0)
    assert r.status_code in (200, 201)
    prod = r.json()
    prod_id = prod["id"] if isinstance(prod, dict) else prod[0]["id"]

    # create variant
    var_payload = {"name": "Default", "sku": "TESTSKU"}
    r = httpx.post(f"{CATALOG}/catalog/product/{prod_id}/variant", json=var_payload, timeout=5.0)
    assert r.status_code in (200, 201)
    variant = r.json()
    variant_id = variant["id"]

    # set inventory +10
    inv_payload = {"variant_id": variant_id, "delta": 10}
    r = httpx.post(f"{CATALOG}/inventory/update", json=inv_payload, timeout=5.0)
    assert r.status_code == 200

    # create cart
    r = httpx.post(f"{CART}/cart/create", json={"session_id": "s1", "user_phone": "+260971000000"}, timeout=5.0)
    assert r.status_code in (200, 201)
    cart = r.json()
    cart_id = cart["id"] if isinstance(cart, dict) else cart[0]["id"]

    # add item quantity 2
    add_payload = {"variant_id": variant_id, "quantity": 2, "unit_price": 100.0}
    r = httpx.post(f"{CART}/cart/{cart_id}/add", json=add_payload, timeout=5.0)
    assert r.status_code == 200

    # checkout
    r = httpx.post(f"{CART}/cart/{cart_id}/checkout", json={}, timeout=10.0)
    assert r.status_code == 200
    out = r.json()
    assert out.get("status") == "checked_out"

    # fetch inventory and assert stock decreased to 8
    r = httpx.get(f"{CATALOG}/inventory/{variant_id}", timeout=5.0)
    assert r.status_code == 200
    inv = r.json()
    assert inv["stock_level"] == 8
