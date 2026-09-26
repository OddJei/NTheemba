"""Focused tests for the developer-only transport simulation laboratory."""

from __future__ import annotations

from fastapi.testclient import TestClient
from ntheemba.config import Settings
from ntheemba.main import create_app

_TOKEN = "transport-gateway-test-token-with-32-characters"


def _app() -> object:
    return create_app(
        Settings(
            environment="test",
            transport_gateway_tokens_json='{"openwa-simulator":"' + _TOKEN + '"}',
        )
    )


def _scenario(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "gatewayId": "openwa-simulator",
        "externalSessionId": "sim-wa-serahs",
        "recipientIdentifier": "+260976078440",
        "senderIdentifier": "+260971234567",
        "text": "I want braids",
    }
    payload.update(overrides)
    return payload


def test_simulation_lab_is_protected_developer_only_and_self_contained() -> None:
    app = _app()
    with TestClient(app) as client:
        page = client.get("/dev/simulation-lab")
        readiness = client.get("/dev/simulation-lab/readiness")

    assert page.status_code == 200
    assert "Ntheemba Simulation Lab" in page.text
    assert "business, shop scope, capability" in page.text
    assert "gateway credential" in page.text
    assert page.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert "unsafe-inline" not in page.headers["content-security-policy"]
    assert readiness.json()["gatewayIds"] == ["openwa-simulator"]
    assert _TOKEN not in page.text
    assert _TOKEN not in readiness.text


def test_lab_submits_the_neutral_envelope_via_transport_v2_without_tenant_fields() -> None:
    app = _app()
    with TestClient(app) as client:
        response = client.post("/dev/simulation-lab/scenarios", json=_scenario())

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["evidence"]["stage"] == "transport.ingress"
    assert payload["evidence"]["inbound"][0]["textLength"] == len("I want braids")
    assert "I want braids" not in str(payload["evidence"])
    assert "+260971234567" not in str(payload["evidence"])
    queued = app.state.storage_runtime.gateway_queue._inbound
    assert len(queued) == 1
    message = next(iter(queued.values())).message
    assert message.channel_instance_id == "sim-wa-serahs"
    assert message.metadata["gateway_id"] == "openwa-simulator"
    assert "business_id" not in message.metadata
    assert "shop_id" not in message.metadata


def test_lab_displays_real_transport_rejections_for_safe_faults() -> None:
    app = _app()
    with TestClient(app) as client:
        response = client.post(
            "/dev/simulation-lab/scenarios", json=_scenario(fault="invalid_credential")
        )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["evidence"] == {
        "stage": "transport.ingress",
        "fault": "invalid_credential",
    }


def test_lab_rejects_configured_gateway_not_explicitly_approved_for_simulation() -> None:
    app = create_app(
        Settings(
            environment="test",
            transport_gateway_tokens_json=(
                '{"openwa-simulator":"' + _TOKEN + '","real-gateway":"'
                + "another-transport-gateway-token-with-32chars"
                + '"}'
            ),
        )
    )
    with TestClient(app) as client:
        response = client.post(
            "/dev/simulation-lab/scenarios", json=_scenario(gatewayId="real-gateway")
        )

    assert response.status_code == 403
    assert "not approved for simulation" in response.json()["detail"]


def test_lab_is_not_registered_in_production_or_openapi() -> None:
    production = create_app(
        Settings(environment="production", dev_tools_enabled=True, docs_enabled=False)
    )
    with TestClient(production) as client:
        assert client.get("/dev/simulation-lab").status_code == 404

    documented = create_app(Settings(environment="test", docs_enabled=True))
    assert all(not path.startswith("/dev/simulation-lab") for path in documented.openapi()["paths"])
