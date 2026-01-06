from __future__ import annotations


def test_create_affiliate_idempotency_key_replays_response(client) -> None:

    r1 = client.post(
        "/affiliates",
        headers={"X-Idempotency-Key": "k-create-aff-1", "X-Correlation-Id": "c-1"},
        json={"name": "Alice", "phone": "+260900000001"},
    )
    assert r1.status_code == 200
    a1 = r1.json()

    r2 = client.post(
        "/affiliates",
        headers={"X-Idempotency-Key": "k-create-aff-1", "X-Correlation-Id": "c-2"},
        json={"name": "Bob", "phone": "+260900000002"},
    )
    assert r2.status_code == 200
    a2 = r2.json()

    assert a2["id"] == a1["id"]
    assert a2["name"] == a1["name"]

    listed = client.get("/affiliates").json()
    assert len(listed) == 1

def test_correlation_id_echoed(client) -> None:
    resp = client.get("/docs", headers={"X-Correlation-Id": "corr-xyz"})
    assert resp.headers.get("X-Correlation-Id") == "corr-xyz"


def test_dashboard_has_expected_keys(client) -> None:
    affiliate = client.post(
        "/affiliates",
        headers={"X-Idempotency-Key": "k-create-aff-dash", "X-Correlation-Id": "c-dash"},
        json={"name": "Dash", "phone": "+260900000003"},
    ).json()

    dash = client.get(f"/affiliates/{affiliate['id']}/dashboard").json()
    for key in ("clicks", "attributions", "conversions", "conversion_rate", "total_earnings"):
        assert key in dash
