"""Transport-neutral v2 gateway boundary tests."""

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from ntheemba.config import Settings
from ntheemba.domain.gateway import OutboundGatewayMessage
from ntheemba.main import create_app

_TOKEN = "transport-gateway-test-token-with-32-characters"
_HEADERS = {
    "Authorization": f"Bearer {_TOKEN}",
    "X-Ntheemba-Gateway-ID": "openwa-simulator",
}


def _payload() -> dict[str, object]:
    return {
        "messageId": "transport-message-1",
        "externalSessionId": "sim-wa-serahs",
        "recipientIdentifier": "+260976078440",
        "senderIdentifier": "+260971234567",
        "text": "I want braids",
        "occurredAt": datetime.now(UTC).isoformat(),
        "correlationId": "transport-request-1",
        "metadata": {"provider_event": "message"},
    }


def _app():
    return create_app(
        Settings(
            environment="test",
            transport_gateway_tokens_json='{"openwa-simulator":"'
            + _TOKEN
            + '"}',
        )
    )


def test_transport_ingress_resolves_the_registered_binding_and_deduplicates() -> None:
    app = _app()
    with TestClient(app) as client:
        first = client.post("/api/v2/transport/inbound", json=_payload(), headers=_HEADERS)
        second = client.post("/api/v2/transport/inbound", json=_payload(), headers=_HEADERS)
    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["duplicate"] is True
    assert len(app.state.storage_runtime.gateway_queue._inbound) == 1


def test_transport_ingress_rejects_replayed_or_unregistered_messages() -> None:
    app = _app()
    expired = _payload()
    expired["occurredAt"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    with TestClient(app) as client:
        stale = client.post("/api/v2/transport/inbound", json=expired, headers=_HEADERS)
        forged = client.post(
            "/api/v2/transport/inbound",
            json=_payload(),
            headers={**_HEADERS, "X-Ntheemba-Gateway-ID": "another-gateway"},
        )
    assert stale.status_code == 409
    assert forged.status_code == 401


def test_gateway_can_claim_only_its_own_outbound_delivery() -> None:
    app = _app()
    with TestClient(app) as client:
        queue = app.state.storage_runtime.gateway_queue
        delivery_id = asyncio.run(
            queue.enqueue_outbound(
                OutboundGatewayMessage(
                    reply_id="reply-1",
                    request_id="request-1",
                    business_id="serahs-glow-lounge",
                    channel_instance_id="sim-wa-serahs",
                    recipient_phone="+260971234567",
                    text="Hello",
                    gateway_id="openwa-simulator",
                    delivery_target="customer:opaque-1",
                    metadata={"idempotency_key": "reply-key-1"},
                )
            )
        )
        claim = client.post(
            "/api/v2/transport/outbound/claim",
            json={"consumerId": "gateway-worker-1"},
            headers=_HEADERS,
        )
        assert claim.status_code == 200
        assert claim.json()["delivery"]["deliveryId"] == delivery_id
        assert claim.json()["delivery"]["deliveryTarget"] == "customer:opaque-1"
        acknowledged = client.post(
            f"/api/v2/transport/outbound/{delivery_id}/ack",
            json={"consumerId": "gateway-worker-1", "outcome": "sent"},
            headers=_HEADERS,
        )
    assert acknowledged.status_code == 204


def test_gateway_reported_failure_is_terminal_and_channel_deduplication_is_scoped() -> None:
    app = _app()
    with TestClient(app) as client:
        first = client.post("/api/v2/transport/inbound", json=_payload(), headers=_HEADERS)
        second_payload = _payload()
        second_payload["externalSessionId"] = "sim-wa-harvest"
        second_payload["recipientIdentifier"] = "+260970000001"
        second = client.post("/api/v2/transport/inbound", json=second_payload, headers=_HEADERS)
        assert first.status_code == second.status_code == 202

        queue = app.state.storage_runtime.gateway_queue
        delivery_id = asyncio.run(
            queue.enqueue_outbound(
                OutboundGatewayMessage(
                    reply_id="reply-failure-1", request_id="request-failure-1",
                    business_id="serahs-glow-lounge", channel_instance_id="sim-wa-serahs",
                    recipient_phone="+260971234567", text="Hello", gateway_id="openwa-simulator",
                )
            )
        )
        assert client.post(
            "/api/v2/transport/outbound/claim",
            json={"consumerId": "gateway-worker-2"},
            headers=_HEADERS,
        ).json()["delivery"]["deliveryId"] == delivery_id
        failed = client.post(
            f"/api/v2/transport/outbound/{delivery_id}/ack",
            json={
                "consumerId": "gateway-worker-2",
                "outcome": "failed",
                "failureCode": "invalid_target",
            },
            headers=_HEADERS,
        )
        assert failed.status_code == 204
        assert delivery_id in queue.outbound_dead_letters
