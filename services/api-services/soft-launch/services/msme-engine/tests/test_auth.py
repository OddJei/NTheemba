from datetime import datetime, timedelta, timezone


def test_register_login_me_and_phone_lookup(client):
    reg = {
        "username": "alice",
        "email": "alice@example.com",
        "phone": "+260700000001",
        "password": "secret123",
        "role": "msme",
    }
    r = client.post("/auth/register", json=reg)
    assert r.status_code == 201
    user_id = r.json()["id"]

    login = client.post("/auth/login", json={"identifier": "alice", "password": "secret123"})
    assert login.status_code == 200
    tokens = login.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["id"] == user_id

    lookup = client.get("/auth/phone/+260700000001")
    assert lookup.status_code == 200
    body = lookup.json()
    assert body["user_id"] == user_id
    assert body["role"] == "msme"


def test_refresh_and_logout(client):
    client.post(
        "/auth/register",
        json={
            "username": "bob",
            "email": "bob@example.com",
            "phone": "+260700000002",
            "password": "secret123",
            "role": "default",
        },
    )
    login = client.post("/auth/login", json={"identifier": "bob", "password": "secret123"})
    tokens = login.json()

    refreshed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200

    logout = client.post("/auth/logout", json={"refresh_token": refreshed.json()["refresh_token"]})
    assert logout.status_code == 200

    # After logout, refresh should fail.
    fail = client.post("/auth/refresh", json={"refresh_token": refreshed.json()["refresh_token"]})
    assert fail.status_code == 401
