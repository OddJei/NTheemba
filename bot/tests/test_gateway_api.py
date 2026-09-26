"""Authenticated durable gateway ingestion API tests."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from ntheemba.config import Settings
from ntheemba.main import create_app


def payload() -> dict[str, object]:
    return {
        "requestId": "REQ-1",
        "messageId": "MSG-1",
        "channelInstanceId": "sim-wa-serahs",
        "provider": "openwa-simulator",
        "recipientPhone": "+260976078440",
        "customerPhone": "+260971234567",
        "text": "I want braids",
        "receivedAt": datetime(2026, 8, 2, 10, 0, tzinfo=UTC).isoformat(),
    }


def test_gateway_inbound_requires_configured_secret() -> None:
    app = create_app(Settings(environment="test", gateway_shared_secret=None))
    with TestClient(app) as client:
        response = client.post("/api/v1/gateway/inbound", json=payload())
    assert response.status_code == 503


def test_gateway_inbound_rejects_wrong_secret() -> None:
    app = create_app(
        Settings(environment="test", gateway_shared_secret="correct-secret")
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/gateway/inbound",
            json=payload(),
            headers={"Authorization": "Bearer wrong-secret"},
        )
    assert response.status_code == 401


def test_gateway_inbound_enqueues_normalized_message() -> None:
    app = create_app(
        Settings(environment="test", gateway_shared_secret="correct-secret")
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/gateway/inbound",
            json=payload(),
            headers={"Authorization": "Bearer correct-secret"},
        )
        assert response.status_code == 202
        claimed = app.state.storage_runtime.gateway_queue._inbound  # noqa: SLF001
        assert len(claimed) == 1
    body = response.json()
    assert body["status"] == "accepted"
    assert body["request_id"] == "REQ-1"
