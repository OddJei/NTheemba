from __future__ import annotations

import re

from fastapi.testclient import TestClient
from ntheemba.config import Settings
from ntheemba.main import create_app

TOKEN = "operator-ui-token-12345678901234567890"


def _app():
    return create_app(
        Settings(
            environment="test",
            dev_tools_enabled=False,
            operator_api_enabled=True,
            operator_api_token=TOKEN,
            operator_api_allowed_actors="operator:ui",
            business_backend="memory",
            customer_backend="memory",
            session_backend="memory",
            gateway_queue_backend="memory",
        )
    )


def _csrf(page: str) -> str:
    return page.split('name="csrf" value="', 1)[1].split('"', 1)[0]


def _action_token(page: str, label: str) -> str:
    match = re.search(
        r'name="action_token" value="([^"]+)".*?<button>' + re.escape(label),
        page,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def _sign_in(client: TestClient) -> None:
    response = client.post(
        "/operator/session",
        data={"actor": "operator:ui", "token": TOKEN},
        follow_redirects=False,
    )
    assert response.status_code == 303


def _add_business(client: TestClient, name: str = "New Shop") -> str:
    add_page = client.get("/operator/businesses/add")
    client.post(
        "/operator/businesses",
        data={"csrf": _csrf(add_page.text), "name": name, "service": "product.catalogue"},
    )
    return "business-" + name.lower().replace(" ", "-")


def test_operator_ui_requires_a_separate_session() -> None:
    with TestClient(_app()) as client:
        assert client.get("/operator", follow_redirects=False).status_code == 401
        _sign_in(client)
        assert client.get("/operator").status_code == 200


def test_operator_ui_uses_a_responsive_product_owned_workspace_shell() -> None:
    with TestClient(_app()) as client:
        login = client.get("/operator/login")
        assert login.status_code == 200
        assert 'class="app-header"' in login.text
        assert 'class="auth-layout"' in login.text
        assert "Developer tools remain separate." in login.text
        assert "@media(max-width:760px)" in login.text

        _sign_in(client)
        overview = client.get("/operator")
        assert 'aria-label="Operator navigation"' in overview.text
        assert "Operator workspace" in overview.text


def test_operator_ui_does_not_render_the_operator_token() -> None:
    with TestClient(_app()) as client:
        _sign_in(client)
        response = client.get("/operator/businesses")
        assert response.status_code == 200
        assert TOKEN not in response.text
        assert "<summary>Technical details" not in response.text


def test_operator_can_add_plain_language_channel_and_connection() -> None:
    with TestClient(_app()) as client:
        _sign_in(client)
        _add_business(client)

        channel_page = client.get("/operator/businesses/business-new-shop/channels")
        csrf = _csrf(channel_page.text)
        channel = client.post(
            "/operator/businesses/business-new-shop/channels",
            data={"csrf": csrf, "phone": "+260970000099"},
            follow_redirects=False,
        )
        assert channel.status_code == 303

        connection_page = client.get("/operator/businesses/business-new-shop/connections")
        csrf = _csrf(connection_page.text)
        connection = client.post(
            "/operator/businesses/business-new-shop/connections",
            data={
                "csrf": csrf,
                "base_url": "https://tradeflow.example/exec",
                "auth_reference": "env:SHOP_TOKEN",
            },
            follow_redirects=False,
        )
        assert connection.status_code == 303
        rendered = client.get("/operator/businesses/business-new-shop/connections")
        assert "Configured" in rendered.text
        assert "tradeflow.example" not in rendered.text
        assert "SHOP_TOKEN" not in rendered.text
        assert "operator-tradeflow-business-new-shop" not in rendered.text
        assert "Advanced connection setup" in rendered.text


def test_operator_service_change_requires_confirmation_and_records_audit() -> None:
    with TestClient(_app()) as client:
        _sign_in(client)
        business_id = _add_business(client)
        services = client.get(f"/operator/businesses/{business_id}/services")
        action_token = _action_token(services.text, "Turn on")

        confirmation = client.post(
            "/operator/confirm",
            data={"csrf": _csrf(services.text), "action_token": action_token},
        )
        assert confirmation.status_code == 200
        assert "Confirm change" in confirmation.text
        assert "makes that customer action available" in confirmation.text

        completed = client.post(
            "/operator/confirm/execute",
            data={"csrf": _csrf(confirmation.text), "action_token": action_token},
            follow_redirects=False,
        )
        assert completed.status_code == 303
        registry = client.app.state.storage_runtime.business_registry
        business = registry._businesses[business_id]
        assert "business.information" in business.declared_capabilities
        assert any(
            event.event_type == "control_plane.capability_changed"
            for event in client.app.state.storage_runtime.audit_sink.events
        )


def test_operator_confirmation_rejects_bad_csrf_and_hides_channel_identifier() -> None:
    with TestClient(_app()) as client:
        _sign_in(client)
        business_id = _add_business(client)
        channel_page = client.get(f"/operator/businesses/{business_id}/channels")
        added = client.post(
            f"/operator/businesses/{business_id}/channels",
            data={"csrf": _csrf(channel_page.text), "phone": "+260970000099"},
            follow_redirects=False,
        )
        assert added.status_code == 303
        rendered = client.get(f"/operator/businesses/{business_id}/channels")
        assert "operator-business-new-shop-260970000099" not in rendered.text
        action_token = _action_token(rendered.text, "Pause")
        rejected = client.post(
            "/operator/confirm",
            data={"csrf": "bad", "action_token": action_token},
        )
        assert rejected.status_code == 403
        confirmation = client.post(
            "/operator/confirm",
            data={"csrf": _csrf(rendered.text), "action_token": action_token},
        )
        assert "stops customer messages" in confirmation.text


def test_operator_status_describes_configuration_not_live_health() -> None:
    with TestClient(_app()) as client:
        _sign_in(client)
        status = client.get("/operator/status")
        assert "Configuration available" in status.text
        assert "Not configured" in status.text
        assert "Working" not in status.text
