from __future__ import annotations


def test_health(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_correlation_id_echoed(client) -> None:
    resp = client.get("/docs", headers={"X-Correlation-Id": "corr-xyz"})
    assert resp.headers.get("X-Correlation-Id") == "corr-xyz"


def test_category_create_idempotency_replays_response(client) -> None:
    r1 = client.post(
        "/catalog/category",
        headers={"X-Idempotency-Key": "k-cat-1", "X-Correlation-Id": "c-1"},
        json={"name": "Food", "business_id": "b-1"},
    )
    assert r1.status_code == 201
    c1 = r1.json()

    r2 = client.post(
        "/catalog/category",
        headers={"X-Idempotency-Key": "k-cat-1", "X-Correlation-Id": "c-2"},
        json={"name": "Different", "business_id": "b-1"},
    )
    assert r2.status_code == 201
    c2 = r2.json()

    assert c2["id"] == c1["id"]
    assert c2["name"] == c1["name"]

    listed = client.get("/catalog/categories", params={"business_id": "b-1"}).json()
    assert len(listed) == 1


def test_product_variant_inventory_flow(client) -> None:
    prod = client.post(
        "/catalog/product",
        headers={"X-Idempotency-Key": "k-prod-1", "X-Correlation-Id": "c-prod"},
        json={
            "business_id": "b-1",
            "name": "Rice",
            "description": "Bag of rice",
            "price": 100.0,
            "currency": "ZMW",
        },
    ).json()

    variant = client.post(
        f"/catalog/product/{prod['id']}/variant",
        headers={"X-Idempotency-Key": "k-var-1", "X-Correlation-Id": "c-var"},
        json={"name": "10kg", "sku": "RICE-10KG", "price_override": 120.0},
    ).json()

    inv_before = client.get(f"/inventory/{variant['id']}").json()
    assert inv_before["stock_level"] == 0

    updated = client.post(
        "/inventory/update",
        headers={"X-Idempotency-Key": "k-inv-1", "X-Correlation-Id": "c-inv"},
        json={"variant_id": variant["id"], "delta": 5, "reserved_delta": 0, "threshold": 2},
    ).json()

    assert updated["variant_id"] == variant["id"]
    assert updated["stock_level"] == 5

    inv_after = client.get(f"/inventory/{variant['id']}").json()
    assert inv_after["stock_level"] == 5

    biz = client.get("/catalog/business/b-1").json()
    assert biz["business_id"] == "b-1"
    assert len(biz["products"]) >= 1
    assert len(biz["variants"]) >= 1
