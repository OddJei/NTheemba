def test_set_and_get_delivery_locations(client):
    # Register a business with embedded owner
    payload = {
        "owner": {
            "username": "owner_dl",
            "email": "owner_dl@example.com",
            "phone": "+260700000010",
            "password": "secret123",
        },
        "name": "DL Shop",
        "location": "Lusaka",
    }

    r = client.post("/business/register", json=payload)
    assert r.status_code == 201
    body = r.json()
    business_id = body["business"]["id"]

    # Login as the owner to obtain token
    login = client.post("/auth/login", json={"identifier": "owner_dl", "password": "secret123"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    # Prepare delivery locations payload
    dl_payload = {
        "Lusaka": {"price_minor": 2500, "currency": "ZMW", "available": True},
        "Ndola": {"price_minor": 3000, "currency": "ZMW"},
    }

    # Update via PUT endpoint
    put = client.put(f"/businesses/{business_id}/delivery-locations", json={"delivery_locations": dl_payload}, headers={"Authorization": f"Bearer {token}"})
    assert put.status_code == 200
    got = put.json()
    assert "Lusaka" in got and got["Lusaka"]["price_minor"] == 2500

    # GET should return same mapping
    g = client.get(f"/businesses/{business_id}/delivery-locations")
    assert g.status_code == 200
    gbody = g.json()
    assert gbody["Ndola"]["price_minor"] == 3000
