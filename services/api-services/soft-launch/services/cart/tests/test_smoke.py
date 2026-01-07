def test_health(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_cart_create_and_add_item(client, inventory_state) -> None:
    r = client.post("/cart/create", json={"session_id": "s-1", "user_phone": "+260900000001", "business_id": "b-1"})
    assert r.status_code == 201
    cart = r.json()
    assert cart["session_id"] == "s-1"

    item = client.post(f"/cart/{cart['id']}/add", json={"variant_id": "v-1", "quantity": 2, "unit_price": 50.0})
    assert item.status_code == 200
    it = item.json()
    assert it["variant_id"] == "v-1"
    assert it["quantity"] == 2
    assert it["reserved_quantity"] == 2
    assert inventory_state["v-1"]["reserved"] == 2

    checkout = client.post(f"/cart/{cart['id']}/checkout")
    assert checkout.status_code == 200
    co = checkout.json()
    assert co["total"] == 100.0
    assert inventory_state["v-1"]["stock_level"] == 98
    assert inventory_state["v-1"]["reserved"] == 0
