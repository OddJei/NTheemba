from __future__ import annotations

from fastapi.testclient import TestClient

from ntheemba.config import Settings
from ntheemba.main import create_app

TOKEN = "operator-control-plane-token-1234567890"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "X-Operator-ID": "operator:james",
    "X-Request-ID": "REQ-OP-1",
}


def _app():
    return create_app(
        Settings(
            environment="test",
            dev_tools_enabled=False,
            operator_api_enabled=True,
            operator_api_token=TOKEN,
        )
    )


def test_operator_api_requires_authentication() -> None:
    app = _app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/operator/control-plane/businesses",
            json={
                "businessId": "BUS-NEW",
                "displayName": "New Business",
                "adapterType": "tradeflow_standard",
                "declaredCapabilities": ["product.catalogue"],
            },
        )
    assert response.status_code == 401


def test_operator_api_registers_business_channel_integration_and_rotates_safely() -> None:
    app = _app()
    with TestClient(app) as client:
        business = client.post(
            "/api/v1/operator/control-plane/businesses",
            headers=HEADERS,
            json={
                "businessId": "BUS-NEW",
                "displayName": "New Business",
                "adapterType": "tradeflow_standard",
                "declaredCapabilities": ["product.catalogue"],
            },
        )
        assert business.status_code == 201, business.text

        shop = client.post(
            "/api/v1/operator/control-plane/businesses/BUS-NEW/shops",
            headers={**HEADERS, "X-Request-ID": "REQ-OP-SHOP"},
            json={
                "shopId": "shop-main",
                "displayName": "Main Shop",
                "isPrimary": True,
                "location": {"province_name": "Lusaka", "district_name": "Lusaka"},
                "hoursStatus": "unverified",
            },
        )
        assert shop.status_code == 201, shop.text
        assert shop.json()["resource_id"] == "shop-main"

        channel = client.post(
            "/api/v1/operator/control-plane/channels",
            headers={**HEADERS, "X-Request-ID": "REQ-OP-2"},
            json={
                "channelInstanceId": "wa-new",
                "provider": "openwa",
                "businessId": "BUS-NEW",
                "phoneE164": "+260970000099",
            },
        )
        assert channel.status_code == 201, channel.text

        integration = client.post(
            "/api/v1/operator/control-plane/integrations",
            headers={**HEADERS, "X-Request-ID": "REQ-OP-3"},
            json={
                "integrationId": "tf-new",
                "businessId": "BUS-NEW",
                "adapterType": "tradeflow_standard",
                "provider": "tradeflow_http",
                "baseUrl": "https://private-tradeflow.example/exec",
                "authReference": "env:BUS_NEW_TOKEN",
                "capabilities": ["product.catalogue"],
            },
        )
        assert integration.status_code == 201, integration.text
        assert "private-tradeflow" not in integration.text
        assert "BUS_NEW_TOKEN" not in integration.text
        assert integration.json()["endpoint_configured"] is True
        assert integration.json()["auth_reference_configured"] is True

        patch = client.patch(
            "/api/v1/operator/control-plane/businesses/BUS-NEW/integrations/tf-new",
            headers={**HEADERS, "X-Request-ID": "REQ-OP-4"},
            json={
                "baseUrl": "https://rotated-private.example/exec",
                "authReference": "env:BUS_NEW_TOKEN_V2",
            },
        )
        assert patch.status_code == 200, patch.text
        assert "rotated-private" not in patch.text
        assert "BUS_NEW_TOKEN_V2" not in patch.text

        capability = client.put(
            "/api/v1/operator/control-plane/businesses/BUS-NEW/capabilities/product.order",
            headers={**HEADERS, "X-Request-ID": "REQ-OP-5"},
            json={"enabled": True, "config": {"collection_only": True}},
        )
        assert capability.status_code == 200, capability.text
        assert "product.order" in capability.json()["capabilities"]

        audit_events = app.state.storage_runtime.audit_sink.events
        assert any(event.event_type == "control_plane.integration_updated" for event in audit_events)
        assert all("private-tradeflow" not in repr(event.data) for event in audit_events)
        assert all("BUS_NEW_TOKEN" not in repr(event.data) for event in audit_events)


def test_operator_api_rejects_cross_business_channel_takeover() -> None:
    app = _app()
    with TestClient(app) as client:
        for business_id in ("BUS-A", "BUS-B"):
            response = client.post(
                "/api/v1/operator/control-plane/businesses",
                headers={**HEADERS, "X-Request-ID": f"REQ-{business_id}"},
                json={
                    "businessId": business_id,
                    "displayName": business_id,
                    "adapterType": "tradeflow_standard",
                    "declaredCapabilities": ["product.catalogue"],
                },
            )
            assert response.status_code == 201
        first = client.post(
            "/api/v1/operator/control-plane/channels",
            headers={**HEADERS, "X-Request-ID": "REQ-CH-A"},
            json={
                "channelInstanceId": "wa-shared",
                "provider": "openwa",
                "businessId": "BUS-A",
                "phoneE164": "+260970000001",
            },
        )
        assert first.status_code == 201
        takeover = client.post(
            "/api/v1/operator/control-plane/channels",
            headers={**HEADERS, "X-Request-ID": "REQ-CH-B"},
            json={
                "channelInstanceId": "wa-shared",
                "provider": "openwa",
                "businessId": "BUS-B",
                "phoneE164": "+260970000002",
            },
        )
        assert takeover.status_code == 400
        assert "another business" in takeover.text


def test_operator_api_rejects_marketplace_as_business_capability_and_allows_platform_channel() -> None:
    app = _app()
    with TestClient(app) as client:
        rejected = client.post(
            "/api/v1/operator/control-plane/businesses",
            headers={**HEADERS, "X-Request-ID": "REQ-MKT-BUS"},
            json={
                "businessId": "BUS-MKT",
                "displayName": "Bad Marketplace Business",
                "adapterType": "tradeflow_standard",
                "declaredCapabilities": ["product.catalogue", "marketplace"],
            },
        )
        assert rejected.status_code == 400
        assert "platform capabilities cannot be assigned" in rejected.text

        platform = client.post(
            "/api/v1/operator/control-plane/channels",
            headers={**HEADERS, "X-Request-ID": "REQ-MKT-PLATFORM"},
            json={
                "channelInstanceId": "ntheemba-marketplace-primary",
                "provider": "waha",
                "phoneE164": "+260970000098",
                "scope": "platform",
                "role": "marketplace",
                "isPrimary": True,
                "externalSessionId": "ntheemba-main",
                "recipientIdentifier": "+260970000098",
            },
        )
        assert platform.status_code == 201, platform.text
        assert platform.json()["business_id"] == "__platform__"
