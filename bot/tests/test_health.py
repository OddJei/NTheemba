"""Tests for liveness and readiness endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Ntheemba Test",
        "version": "0.1.0-test",
        "environment": "test",
    }


def test_readiness_endpoint_has_no_external_phase_zero_dependencies(
    client: TestClient,
) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "application": {
                "status": "ready",
                "detail": "FastAPI application initialized",
            },
            "observability": {
                "status": "ready",
                "detail": "2 trace sink(s) configured; 0 emission failure(s)",
            },
            "storage": {
                "status": "ready",
                "detail": "Redis not required; PostgreSQL not required",
            },
        },
    }


def test_documentation_is_disabled_in_test_settings(client: TestClient) -> None:
    response = client.get("/docs")

    assert response.status_code == 404
