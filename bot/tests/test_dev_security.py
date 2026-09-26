"""HTTP security tests for Phase 11.7 developer tooling."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from ntheemba.config import Settings
from ntheemba.main import create_app
from pydantic import ValidationError

_TOKEN = "phase-11-7-developer-token-value-1234567890"


def secured_client() -> TestClient:
    app = create_app(
        Settings(
            environment="test",
            docs_enabled=True,
            dev_tools_token=_TOKEN,
        )
    )
    return TestClient(app)


def test_console_requires_explicit_login_and_uses_an_opaque_http_only_session() -> None:
    with secured_client() as client:
        console = client.get("/dev/console")
        login = client.post(
            "/dev/auth/session",
            data={"token": _TOKEN, "next": "/dev/console"},
            follow_redirects=False,
        )
        simulator = client.get("/dev/simulator")
        workspace = client.get("/dev/simulator/workspace")
        denied = client.get("/dev/traces")
        allowed = client.get(
            "/dev/traces",
            headers={"Authorization": f"Bearer {_TOKEN}"},
        )

    assert console.status_code == 200
    assert console.history and console.history[0].status_code == 303
    assert login.status_code == 303
    assert simulator.status_code == 200
    assert workspace.status_code == 200
    assert _TOKEN not in console.text
    assert _TOKEN not in simulator.text
    assert _TOKEN not in workspace.text
    assert denied.status_code == 200
    assert "httponly" in login.headers["set-cookie"].lower()
    assert "samesite=strict" in login.headers["set-cookie"].lower()
    assert _TOKEN not in login.headers["set-cookie"]
    assert allowed.status_code == 200


def test_explicit_token_header_is_supported() -> None:
    with secured_client() as client:
        response = client.get(
            "/dev/dependencies",
            headers={"X-Ntheemba-Dev-Token": _TOKEN},
        )

    assert response.status_code == 200


def test_wrong_token_is_rejected_without_echoing_it() -> None:
    wrong = "wrong-developer-token-that-is-long-enough"
    with secured_client() as client:
        response = client.get(
            "/dev/traces",
            headers={"Authorization": f"Bearer {wrong}"},
        )

    assert response.status_code == 401
    assert wrong not in response.text
    assert response.json() == {"detail": "Developer tooling authentication required."}


def test_cross_origin_requests_are_rejected() -> None:
    with secured_client() as client:
        response = client.put(
            "/dev/dependencies/audit",
            json={"always_fail": True},
            headers={
                "Authorization": f"Bearer {_TOKEN}",
                "Origin": "https://attacker.example",
            },
        )

    assert response.status_code == 403


def test_same_origin_request_is_allowed() -> None:
    with secured_client() as client:
        response = client.put(
            "/dev/dependencies/audit",
            json={"always_fail": True},
            headers={
                "Authorization": f"Bearer {_TOKEN}",
                "Origin": "http://testserver",
            },
        )

    assert response.status_code == 200


def test_null_origin_is_permitted_only_for_the_token_bearing_login_form() -> None:
    with secured_client() as client:
        login = client.post(
            "/dev/auth/session",
            data={"token": _TOKEN, "next": "/dev/simulation-lab"},
            headers={"Origin": "null"},
            follow_redirects=False,
        )
        protected = client.put(
            "/dev/dependencies/audit",
            json={"always_fail": True},
            headers={"Authorization": f"Bearer {_TOKEN}", "Origin": "null"},
        )

    assert login.status_code == 303
    assert protected.status_code == 403


def test_unapproved_socket_peer_is_rejected_and_forwarding_headers_are_ignored() -> None:
    app = create_app(Settings(environment="development", docs_enabled=False))
    with TestClient(app, client=("203.0.113.10", 50000)) as client:
        response = client.get(
            "/dev/console",
            headers={"X-Forwarded-For": "127.0.0.1"},
        )

    assert response.status_code == 403


def test_approved_remote_network_requires_and_accepts_token() -> None:
    app = create_app(
        Settings(
            environment="development",
            docs_enabled=False,
            dev_tools_allowed_networks="192.0.2.0/24",
            dev_tools_token=_TOKEN,
        )
    )
    with TestClient(app, client=("192.0.2.15", 50000)) as client:
        denied = client.get("/dev/traces")
        allowed = client.get(
            "/dev/traces",
            headers={"Authorization": f"Bearer {_TOKEN}"},
        )

    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_remote_network_cannot_be_enabled_without_token() -> None:
    with pytest.raises(ValidationError, match="dev_tools_token is required"):
        Settings(
            environment="development",
            dev_tools_allowed_networks="192.0.2.0/24",
            dev_tools_token=None,
        )


def test_short_developer_token_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(environment="test", dev_tools_token="too-short")


def test_developer_tools_can_be_disabled() -> None:
    app = create_app(
        Settings(
            environment="test",
            docs_enabled=False,
            dev_tools_enabled=False,
        )
    )
    with TestClient(app) as client:
        assert client.get("/dev/console").status_code == 404
        assert client.get("/dev/traces").status_code == 404

    assert not hasattr(app.state, "trace_sink")
    assert not hasattr(app.state, "fake_dependency_controller")


def test_developer_responses_receive_defensive_headers() -> None:
    with secured_client() as client:
        response = client.get(
            "/dev/traces",
            headers={"Authorization": f"Bearer {_TOKEN}"},
        )

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"


def test_developer_routes_are_excluded_from_openapi() -> None:
    app = create_app(Settings(environment="test", docs_enabled=True))
    paths = app.openapi()["paths"]

    assert all(not path.startswith("/dev") for path in paths)
