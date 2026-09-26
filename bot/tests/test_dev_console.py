"""HTTP tests for the Phase 11.5 developer trace console."""

from __future__ import annotations

from fastapi.testclient import TestClient
from ntheemba.config import Settings
from ntheemba.main import create_app


def test_console_is_available_in_test_environment(client: TestClient) -> None:
    response = client.get("/dev/console")

    assert response.status_code == 200
    assert "Ntheemba Developer Trace Console" in response.text
    assert "/dev/traces" in response.text
    assert "/dev/health/tracing" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"
    csp = response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in csp
    assert "'unsafe-inline'" not in csp
    assert "script-src 'nonce-" in csp
    assert "style-src 'nonce-" in csp
    assert 'nonce="' in response.text


def test_console_is_not_exposed_in_production() -> None:
    app = create_app(
        Settings(
            environment="production",
            docs_enabled=False,
            gateway_shared_secret=None,
            redis_url=None,
        )
    )

    with TestClient(app) as client:
        assert client.get("/dev/console").status_code == 404
        assert client.get("/dev/traces").status_code == 404


def test_console_is_excluded_from_openapi(client: TestClient) -> None:
    response = client.get("/dev/console")
    assert response.status_code == 200

    app = create_app(Settings(environment="test", docs_enabled=True))
    schema = app.openapi()
    assert "/dev/console" not in schema["paths"]
