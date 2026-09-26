"""HTTP tests for Phase 11.6 fake dependency controls."""

from __future__ import annotations

from fastapi.testclient import TestClient
from ntheemba.config import Settings
from ntheemba.main import create_app


def test_lists_default_fake_dependencies(client: TestClient) -> None:
    response = client.get("/dev/dependencies")

    assert response.status_code == 200
    body = response.json()
    assert [item["dependency"] for item in body] == [
        "audit",
        "deduplication",
        "interpreter",
        "ncpc",
        "publisher",
        "session_lock",
        "session_repository",
        "tradeflow",
    ]
    assert all(item["latency_ms"] == 0 for item in body)


def test_configures_and_fetches_dependency(client: TestClient) -> None:
    payload = {
        "latency_ms": 150,
        "fail_next": 2,
        "always_fail": False,
        "failure_message": "TradeFlow test outage",
        "operations": ["create_order_request"],
    }

    response = client.put("/dev/dependencies/tradeflow", json=payload)

    assert response.status_code == 200
    assert response.json() == {"dependency": "tradeflow", **payload}
    assert client.get("/dev/dependencies/tradeflow").json() == response.json()


def test_unknown_dependency_returns_404(client: TestClient) -> None:
    assert client.get("/dev/dependencies/missing").status_code == 404
    assert client.delete("/dev/dependencies/missing").status_code == 404


def test_fail_next_probe_is_consumed(client: TestClient) -> None:
    client.put(
        "/dev/dependencies/publisher",
        json={"fail_next": 1, "failure_message": "Publisher unavailable"},
    )

    failed = client.post(
        "/dev/dependencies/publisher/probe",
        json={"operation": "publish"},
    )
    passed = client.post(
        "/dev/dependencies/publisher/probe",
        json={"operation": "publish"},
    )

    assert failed.status_code == 503
    assert failed.json()["detail"]["code"] == "FAKE_DEPENDENCY_FAILURE"
    assert failed.json()["detail"]["message"] == "Publisher unavailable"
    assert passed.status_code == 200
    assert passed.json()["status"] == "passed"


def test_operation_filter_targets_only_selected_calls(client: TestClient) -> None:
    client.put(
        "/dev/dependencies/ncpc",
        json={"fail_next": 1, "operations": ["search_products"]},
    )

    ignored = client.post(
        "/dev/dependencies/ncpc/probe",
        json={"operation": "get_product"},
    )
    targeted = client.post(
        "/dev/dependencies/ncpc/probe",
        json={"operation": "search_products"},
    )

    assert ignored.status_code == 200
    assert targeted.status_code == 503


def test_resets_selected_dependency(client: TestClient) -> None:
    client.put("/dev/dependencies/audit", json={"always_fail": True})

    response = client.delete("/dev/dependencies/audit")

    assert response.status_code == 200
    assert response.json()["always_fail"] is False
    assert response.json()["fail_next"] == 0


def test_resets_all_dependencies(client: TestClient) -> None:
    client.put("/dev/dependencies/audit", json={"always_fail": True})
    client.put("/dev/dependencies/publisher", json={"latency_ms": 50})

    response = client.post("/dev/dependencies/reset")

    assert response.status_code == 204
    behaviors = client.get("/dev/dependencies").json()
    assert all(not item["always_fail"] and item["latency_ms"] == 0 for item in behaviors)


def test_invalid_control_values_return_422(client: TestClient) -> None:
    response = client.put(
        "/dev/dependencies/audit",
        json={"latency_ms": 30_001},
    )

    assert response.status_code == 422


def test_dependency_controls_are_not_exposed_in_production() -> None:
    app = create_app(
        Settings(
            environment="production",
            docs_enabled=False,
            gateway_shared_secret=None,
            redis_url=None,
        )
    )

    with TestClient(app) as client:
        assert client.get("/dev/dependencies").status_code == 404
        assert client.post("/dev/dependencies/reset").status_code == 404


def test_console_exposes_dependency_controls(client: TestClient) -> None:
    response = client.get("/dev/console")

    assert response.status_code == 200
    assert "Fake dependency controls" in response.text
    assert "/dev/dependencies" in response.text
