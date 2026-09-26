"""Protected Phase 12 storage diagnostic tests."""

from fastapi.testclient import TestClient

from ntheemba.config import Settings
from ntheemba.main import create_app


def test_storage_status_reports_all_configured_backends(client: TestClient) -> None:
    response = client.get("/dev/storage")

    assert response.status_code == 200
    body = response.json()
    assert body["opened"] is True
    assert body["session_backend"] == "memory"
    assert body["customer_backend"] == "memory"
    assert body["business_backend"] == "memory"
    assert body["gateway_queue_backend"] == "memory"
    assert body["redis_ready"] is True
    assert body["postgres_ready"] is True


def test_storage_business_registry_lists_exact_channel_mappings(client: TestClient) -> None:
    response = client.get("/dev/storage/businesses")

    assert response.status_code == 200
    body = response.json()
    assert {item["business_id"] for item in body["businesses"]} == {
        "harvest-big-shop",
        "amac-enterprise",
        "serahs-glow-lounge",
    }
    channels = {item["channel_instance_id"]: item for item in body["channels"]}
    assert channels["sim-wa-serahs"]["business_id"] == "serahs-glow-lounge"


def test_storage_consent_endpoint_records_explicit_permission(client: TestClient) -> None:
    response = client.post(
        "/dev/storage/consents",
        json={
            "customer_id": "CUST-1",
            "consent_type": "cross_business_name",
            "granted": True,
            "source": "test",
        },
    )

    assert response.status_code == 200
    assert response.json()["granted"] is True


def test_storage_routes_are_not_registered_in_production() -> None:
    app = create_app(
        Settings(environment="production", dev_tools_enabled=False, docs_enabled=False)
    )
    with TestClient(app) as client:
        assert client.get("/dev/storage").status_code == 404
